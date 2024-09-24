import csv
from django.views.generic.edit import FormView
from django.urls import reverse_lazy
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from .forms import CSVUploadForm
from django.views.generic import ListView
from django.db.models import Q
from .models import Survey, RepresentedVariable, ConceptualVariable, Category, BindingSurveyRepresentedVariable
from django.http import JsonResponse
from django.db import transaction
from .documents import BindingSurveyDocument

from elasticsearch_dsl import Search, A


class CSVUploadView(FormView):
    template_name = 'upload_csv.html'
    form_class = CSVUploadForm
    success_url = reverse_lazy('app:representedvariable_search')  # Redirection vers la vue de recherche
    required_columns = ['ddi', 'title', 'variable_name', 'variable_label', 'question_text', 'category_label']

    @transaction.atomic
    def form_valid(self, form):
        print("Formulaire valide, début du traitement")
        csv_file = form.cleaned_data['csv_file']
        decoded_file = csv_file.read().decode('utf-8').splitlines()
        sample = '\n'.join(decoded_file[:2])
        sniffer = csv.Sniffer()
        delimiter = sniffer.sniff(sample).delimiter
        reader = csv.DictReader(decoded_file, delimiter=delimiter)

        missing_columns = self.validate_columns(reader.fieldnames)
        if missing_columns:
            print(f"Colonnes manquantes: {missing_columns}")
            return self.render_with_errors(form, missing_columns)

        try:
            num_records = self.process_csv(reader)  # Traiter le fichier et obtenir le nombre d'enregistrements
            messages.success(self.request,
                             f"Le fichier CSV a été traité avec succès. {num_records} lignes ont été analysées.")
            return super().form_valid(form)

        except Exception as e:
            error_message = f"Une erreur s'est produite lors du traitement du fichier CSV : {str(e)}"
            messages.error(self.request, error_message)
            return self.render_with_errors(form)

    def validate_columns(self, fieldnames):
        """Retourne une liste des colonnes manquantes."""
        return [col for col in self.required_columns if col not in fieldnames]

    def render_with_errors(self, form, missing_columns=None):
        context = {'form': form}
        if missing_columns:
            context['missing_columns'] = missing_columns
        return render(self.request, self.template_name, context)

    def process_csv(self, reader):
        num_records = 0
        for line_number, row in enumerate(reader, start=1):
            try:
                survey = self.get_or_create_survey(row)
                represented_variable = self.get_or_create_represented_variable(row, survey)
                self.get_or_create_binding(survey, represented_variable, row['variable_name'])
                num_records += 1  # Incrémentez le compteur pour chaque ligne traitée
            except Exception as e:
                error_message = f"Erreur à la ligne {line_number}: {row}. Détail de l'erreur: {str(e)}"
                print(error_message)
                raise Exception(error_message)  # Relève l'exception pour annuler la transaction
        return num_records  # R

    def get_or_create_survey(self, row):
        """Retourne une instance de Survey, créant une nouvelle instance si nécessaire."""
        survey, _ = Survey.objects.get_or_create(
            external_ref=row['ddi'],
            name=row['title']
        )
        return survey

    def get_or_create_represented_variable(self, row, survey):
        """Retourne une instance de RepresentedVariable, créant une nouvelle instance si nécessaire."""
        name_question = row['question_text']
        var_represented = RepresentedVariable.objects.filter(question_text=name_question).first()

        if var_represented and name_question == var_represented.question_text:
            if self.check_category(row['category_label'], var_represented.categories):
                return var_represented
            else:
                return self.create_new_represented_variable(row, var_represented.conceptual_var, name_question)
        else:
            return self.create_new_represented_variable(row, ConceptualVariable.objects.create(), name_question)

    def create_new_represented_variable(self, row, conceptual_var, name_question):
        """Crée une nouvelle instance de RepresentedVariable et l'associe à des catégories."""
        new_represented_var = RepresentedVariable.objects.create(
            conceptual_var=conceptual_var,
            question_text=name_question
        )
        new_categories = self.create_new_categories(row['category_label'])
        new_represented_var.categories.set(new_categories)
        return new_represented_var

    def create_new_categories(self, csv_category_string):
        """Crée et retourne une liste de nouvelles instances de Category basées sur une chaîne CSV."""
        categories = []
        if csv_category_string:
            parsed_categories = self.parse_categories(csv_category_string)
            for code, label in parsed_categories:
                category, _ = Category.objects.get_or_create(
                    code=code,
                    category_label=label
                )
                categories.append(category)
        return categories

    def get_or_create_binding(self, survey, represented_variable, variable_name):
        """Crée ou récupère une instance de BindingSurveyRepresentedVariable."""
        BindingSurveyRepresentedVariable.objects.get_or_create(
            survey=survey,
            variable=represented_variable,
            variable_name=variable_name
        )

    def check_category(self, csv_category_string, existing_categories):
        """Vérifie si les catégories CSV correspondent aux catégories existantes."""
        csv_categories = self.parse_categories(csv_category_string) if csv_category_string else []
        existing_categories_list = [(category.code, category.category_label) for category in existing_categories.all()]
        return set(csv_categories) == set(existing_categories_list)

    def parse_categories(self, csv_category_string):
        """Parse une chaîne de catégories CSV en une liste de tuples (code, label)."""
        categories = []
        csv_category_pairs = csv_category_string.split(" | ")
        for pair in csv_category_pairs:
            code, label = pair.split(",", 1)
            categories.append((code.strip(), label.strip()))
        return categories


class RepresentedVariableSearchView(ListView):
    model = RepresentedVariable
    template_name = 'homepage.html'  # Nom du template
    context_object_name = 'variables'  # Nom du contexte utilisé dans le template

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['surveys'] = Survey.objects.all()
        context['success_message'] = self.request.GET.get('success_message', None)
        context['upload_stats'] = self.request.GET.get('upload_stats', None)
        return context




def search_results(request):
    search_location = request.GET.get('search_location', 'questions')
    studies = Survey.objects.all()
    context = locals()
    return render(request, 'search_results.html', context)


def search_results_data(request):
    # Récupérer les valeurs de la recherche et du filtre d'études
    search_value = request.GET.get('q', '').strip().lower()
    search_location = request.GET.get('search_location', 'questions')
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    study_filter = request.GET.getlist('study[]', None)

    # Convertir le filtre en liste d'entiers si nécessaire
    study_filter = [int(study_id) for study_id in study_filter if study_id.isdigit()]

    # Initialisation de la recherche avec Elasticsearch pour BindingSurveyRepresentedVariable
    search = BindingSurveyDocument.search()

    if search_value:
        if search_location == 'questions':
            # Priorité aux correspondances exactes via 'should'
            search = search.query(
                'bool',
                should=[
                    # Recherche exacte avec un boost élevé
                    {"term": {"variable.question_text.keyword": {"value": search_value, "boost": 10}}},
                    # Recherche par phrase pour des correspondances proches
                    {"match_phrase": {"variable.question_text": {"query": search_value, "boost": 5}}},
                    # Recherche par préfixe avec le boost le plus bas
                    {"match_phrase_prefix": {"variable.question_text": {"query": search_value, "boost": 1}}}
                ],
                minimum_should_match=1
            )
        elif search_location == 'categories':
            search = search.query('nested', path='variable.categories', query={
                'bool': {
                    'should': [
                        # Correspondance exacte sur la catégorie avec un boost élevé
                        {"term": {"variable.categories.category_label.keyword": {"value": search_value, "boost": 10}}},
                        # Correspondance par phrase pour des résultats proches
                        {"match_phrase": {"variable.categories.category_label": {"query": search_value, "boost": 5}}},
                        # Correspondance par préfixe avec un boost plus bas
                        {"match_phrase_prefix": {"variable.categories.category_label": {"query": search_value, "boost": 1}}}
                    ],
                    "minimum_should_match": 1
                }
            })

        # Ajout du highlighting pour mettre en valeur les termes recherchés
        search = search.highlight_options(pre_tags=["<mark style='background-color: yellow;'>"], post_tags=["</mark>"]) \
                       .highlight('variable.question_text', fragment_size=150) \
                       .highlight('variable.categories.category_label', fragment_size=150)
    # Appliquer le filtre par étude si nécessaire
    if len(study_filter) > 0:
        search = search.filter('terms', **{"survey.id": study_filter})

    # Exécuter la recherche pour obtenir les résultats paginés
    response = search[start:start+length].execute()
    # Récupérer le nombre total de documents correspondants avant et après filtrage
    total_records = BindingSurveyDocument.search().count()
    filtered_records = response.hits.total.value  # Nombre de documents filtrés

    # Formatage des résultats pour DataTables
    data = []
    for result in response.hits:
        highlighted_question = result.variable.question_text if hasattr(result.variable, 'question_text') else "N/A"
        if 'highlight' in result.meta and 'variable.question_text' in result.meta.highlight:
            highlighted_question = result.meta.highlight['variable.question_text'][0]

        category_matched = None
        other_categories = []
        if search_location == 'categories':
            if 'highlight' in result.meta and 'variable.categories.category_label' in result.meta.highlight:
                category_matched = result.meta.highlight['variable.categories.category_label'][0]

            if hasattr(result.variable, 'categories'):
                for category in result.variable.categories:
                        other_categories.append(category.category_label)

        data.append({
            "id": result.meta.id,  # ID de la liaison
            "variable_name": result.variable_name if hasattr(result, 'variable_name') else "N/A",
            "question_text": highlighted_question,  # Texte de la question avec surbrillance si disponible
            "survey_name": result.survey.name if hasattr(result, 'survey') else "N/A",
            "notes": result.notes if hasattr(result, 'notes') else "N/A",
            "category_matched": category_matched,
            "other_categories": other_categories,
        })

    # Retourner la réponse au format JSON pour DataTables
    return JsonResponse({
        "recordsTotal": total_records,
        "recordsFiltered": filtered_records,
        "draw": int(request.GET.get('draw', 1)),
        "data": data
    })





import re
def autocomplete(request):
    search_value = request.GET.get('q', '').lower()
    search_location = request.GET.get('location', 'questions')
    
    s = Search(using='default', index='binding_survey_variables')

    if search_location == 'questions':
        s = s.query(
            "match",
            variable__question_text={
                "query": search_value,
                "fuzziness": "AUTO",  # Autorise la recherche floue
                "operator": "and"  # Rend la recherche plus stricte pour les multi-mots
            }
        )
    elif search_location == 'categories':
        s = s.query(
            "nested",
            path="variable.categories",
            query={
                "match": {
                    "variable.categories.category_label": {
                        "query": search_value,
                        "fuzziness": "AUTO"  # Active la recherche floue dans les catégories également
                    }
                }
            }
        )

    # Log de la requête et de la réponse
    response = s.execute()

    suggestions = []
    seen = set()
    for hit in response.hits:
        if search_location == 'questions':
            text = hit.variable.question_text.lower()
            if text not in seen:
                seen.add(text)
                suggestions.append(text)
        elif search_location == 'categories' and hit.variable.categories:
            for category in hit.variable.categories:
                if search_value in category.category_label.lower():
                    text = category.category_label.lower()
                    if text not in seen:
                        seen.add(text)
                        suggestions.append(text)

    return JsonResponse({"suggestions": suggestions})




from django.http import HttpResponse
from django.views import View
class ExportQuestionsCSVView(View):
    def get(self, request, *args, **kwargs):
        # Créer la réponse CSV
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="questions_export.csv"'

        # Définir les colonnes du CSV
        writer = csv.writer(response)
        writer.writerow(['ddi', 'title', 'variable_name', 'variable_label', 'question_text', 'category_label'])

        # Récupérer toutes les questions et les informations associées
        questions = RepresentedVariable.objects.all()
        for question in questions:
            # Récupérer les liaisons entre les surveys et les variables représentées
            binding = BindingSurveyRepresentedVariable.objects.filter(variable=question).first()

            if binding:
                survey = binding.survey  # Récupérer le survey associé à cette variable représentée
                variable_name = binding.variable_name
            else:
                survey = None
                variable_name = ''

            # Récupérer les catégories associées
            categories = " | ".join ([f"{cat.code},{cat.category_label}" for cat in question.categories.all()])
            
            writer.writerow([
                survey.external_ref if survey else '',  # DDI
                survey.name if survey else '',          # Title
                variable_name,                          # Variable Name
                question.internal_label or '',          # Variable Label
                question.question_text or '',           # Question Text
                categories                              # Category Label
            ])

        return response
def export_page(request):
    return render(request, 'export_csv.html')

class QuestionDetailView(View): 
    def get(self, request, id, *args, **kwargs):
        question = get_object_or_404(BindingSurveyRepresentedVariable, id=id)
        question_represented_var = question.variable
        question_conceptual_var = question_represented_var.conceptual_var
        question_survey = question.survey
        categories = question.variable.categories.all()
        context = locals()
        return render(request, 'question_detail.html', context)

def similar_representative_variable_questions(request, question_id):
    question = get_object_or_404(BindingSurveyRepresentedVariable, id=question_id)

    rep_variable = question.variable 
    questions_from_rep_variable = BindingSurveyRepresentedVariable.objects.filter(variable=rep_variable).exclude(id=question_id)

    data = []
    for similar_question in questions_from_rep_variable:
        data.append({
            "id": similar_question.id,
            "question_text": similar_question.variable.question_text,
            "internal_label": similar_question.variable.internal_label or "N/A",
            "survey" : similar_question.survey.name
        })

    return JsonResponse({
        "recordsTotal": len(questions_from_rep_variable),
        "recordsFiltered": len(questions_from_rep_variable),
        "data": data
    })


def similar_conceptual_variable_questions(request, question_id):
    question = get_object_or_404(BindingSurveyRepresentedVariable, id=question_id)
    rep_variable = question.variable 

    conceptual_variable = rep_variable.conceptual_var

    questions_from_conceptual_variable = BindingSurveyRepresentedVariable.objects.filter(variable__conceptual_var=conceptual_variable).exclude(id=question_id)

    data = []
    for similar_question in questions_from_conceptual_variable:
        data.append({
            "id": similar_question.id,
            "question_text": similar_question.variable.question_text,
            "internal_label": similar_question.variable.internal_label or "N/A",
            "survey" : similar_question.survey.name
        })

    return JsonResponse({
        "recordsTotal": len(questions_from_conceptual_variable),
        "recordsFiltered": len(questions_from_conceptual_variable),
        "data": data
    })