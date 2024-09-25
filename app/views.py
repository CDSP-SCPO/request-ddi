import csv
from django.views.generic.edit import FormView
from django.urls import reverse_lazy
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from .forms import CSVUploadForm, XMLUploadForm
from django.views.generic import ListView
from django.db.models import Q
from .models import Survey, RepresentedVariable, ConceptualVariable, Category, BindingSurveyRepresentedVariable
from django.http import JsonResponse
from django.db import transaction
from .documents import BindingSurveyDocument
from bs4 import BeautifulSoup

from elasticsearch_dsl import Search, A


from abc import ABC, abstractmethod
from django.views.generic.edit import FormView
from django.contrib import messages
from django.urls import reverse_lazy
from django.db import transaction
import csv
from bs4 import BeautifulSoup

class BaseUploadView(FormView, ABC):
    template_name = ''
    form_class = None
    success_url = reverse_lazy('app:representedvariable_search')

    @transaction.atomic
    def form_valid(self, form):
        print("Formulaire valide, début du traitement")
        data = self.get_data(form)
        question_datas = list(self.convert_data(data))

        try:
            num_records = self.process_data(question_datas)
            messages.success(self.request, f"Le fichier a été traité avec succès. {num_records} lignes ont été analysées.")
            return super().form_valid(form)

        except Exception as e:
            messages.error(self.request, f"Erreur lors du traitement des données : {str(e)}")
            return self.form_invalid(form)

    @abstractmethod
    def get_data(self, form):
        """Méthode pour obtenir les données du formulaire."""
        pass

    @abstractmethod
    def convert_data(self, content):
        """Méthode pour extraire les données."""
        pass

    @abstractmethod
    def process_data(self, question_datas):
        """Méthode pour traiter les données."""
        pass

    def get_or_create_survey(self, doi, title):
        """Retourne une instance de Survey, créant une nouvelle instance si nécessaire."""
        survey, _ = Survey.objects.get_or_create(external_ref=doi, name=title)
        return survey

    def get_or_create_binding(self, survey, represented_variable, variable_name):
        """Crée ou récupère une instance de BindingSurveyRepresentedVariable."""
        BindingSurveyRepresentedVariable.objects.get_or_create(
            survey=survey,
            variable=represented_variable,
            variable_name=variable_name
        )

    def check_category(self, category_string, existing_categories):
        """Vérifie si les catégories correspondent aux catégories existantes."""
        csv_categories = self.parse_categories(category_string) if category_string else []
        existing_categories_list = [(category.code, category.category_label) for category in existing_categories.all()]
        return set(csv_categories) == set(existing_categories_list)

    def parse_categories(self, category_string):
        """Parse une chaîne de catégories en une liste de tuples (code, label)."""
        categories = []
        csv_category_pairs = category_string.split(" | ")
        for pair in csv_category_pairs:
            code, label = pair.split(",", 1)
            categories.append((code.strip(), label.strip()))
        return categories



class CSVUploadView(BaseUploadView):
    template_name = 'upload_csv.html'
    form_class = CSVUploadForm
    required_columns = ['ddi', 'title', 'variable_name', 'variable_label', 'question_text', 'category_label']

    def get_data(self, form):
        return form.cleaned_data['csv_file']  # Données CSV

    def convert_data(self, content):
        """Convertit le contenu CSV en un format traité."""
        return csv.DictReader(content)  # Convertir directement en DictReader

    def process_data(self, question_datas):
        num_records = 0
        for line_number, row in enumerate(question_datas, start=1):
            try:
                survey = self.get_or_create_survey(row['ddi'], row['title'])
                represented_variable = self.get_or_create_represented_variable(row, survey)
                self.get_or_create_binding(survey, represented_variable, row['variable_name'])
                num_records += 1
            except Exception as e:
                error_message = f"Erreur à la ligne {line_number}: {row}. Détail de l'erreur: {str(e)}"
                print(error_message)
                raise Exception(error_message)  # Relève l'exception pour annuler la transaction
        return num_records

    def get_or_create_represented_variable(self, row, survey):
        """Retourne une instance de RepresentedVariable, créant une nouvelle instance si nécessaire."""
        name_question = row['question_text']
        var_represented = RepresentedVariable.objects.filter(question_text=name_question)

        if var_represented.exists():
            for var in var_represented:
                if self.check_category(row['category_label'], var.categories):
                    return var
            return self.create_new_represented_variable(row, var_represented[0].conceptual_var, name_question)
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



class XMLUploadView(BaseUploadView):
    template_name = 'upload_xml.html'
    form_class = XMLUploadForm

    def get_data(self, form):
        return form.cleaned_data['xml_file']  # Données XML

    def convert_data(self, content):
        """Extrait les données du contenu XML."""
        soup = BeautifulSoup(content, "xml")
        doi = soup.find("IDNo", attrs={"agency": "DataCite"}).text.strip() if soup.find("IDNo", attrs={"agency": "DataCite"}) else soup.find("IDNo").text.strip()
        title = soup.find("titl").text.strip()

        for line in soup.find_all("var"):
            cat_to_add = " | ".join([','.join([cat.find("catValu").text.strip() if cat.find("catValu") else '',
                                               cat.find("labl").text.strip() if cat.find("labl") else ''])
                                     for cat in line.find_all("catgry")
                                     ])
            question_data = [
                doi,
                title,
                line["name"].strip(),
                line.find("labl").text.strip() if line.find("labl") else "",
                line.find("qstnLit").text.strip() if line.find("qstnLit") else "",
                cat_to_add,
                line.find("universe").text.strip() if line.find("universe") else "",
                line.find("notes").text.strip() if line.find("notes") else "",
            ]
            yield question_data

    def process_data(self, question_datas):
        num_records = 0
        for question_data in question_datas:
            doi, title, variable_name, variable_label, question_text, category_label, universe, notes = question_data
            survey = self.get_or_create_survey(doi, title)
            represented_variable = self.get_or_create_represented_variable(variable_name, question_text, category_label)
            self.get_or_create_binding(survey, represented_variable, variable_name)
            num_records += 1  # Incrémentez le compteur pour chaque ligne traitée

        return num_records

    def get_or_create_represented_variable(self, variable_name, question_text, category_label):
        """Retourne une instance de RepresentedVariable, créant une nouvelle instance si nécessaire."""
        var_represented = RepresentedVariable.objects.filter(question_text=question_text)

        if var_represented.exists():
            for var in var_represented:
                if self.check_category(category_label, var.categories):
                    return var
            return self.create_new_represented_variable(variable_name, var_represented[0].conceptual_var, question_text, category_label)
        else:
            return self.create_new_represented_variable(variable_name, ConceptualVariable.objects.create(), question_text, category_label)

    def create_new_represented_variable(self, variable_name, conceptual_var, question_text, category_label):
        """Crée une nouvelle instance de RepresentedVariable et l'associe à des catégories."""
        new_represented_var = RepresentedVariable.objects.create(
            conceptual_var=conceptual_var,
            question_text=question_text
        )
        self.create_new_categories(category_label, new_represented_var)
        return new_represented_var

    def create_new_categories(self, category_string, represented_variable):
        """Crée et associe de nouvelles catégories à une variable représentée."""
        if category_string:
            parsed_categories = self.parse_categories(category_string)
            for code, label in parsed_categories:
                category, _ = Category.objects.get_or_create(code=code, category_label=label)
                represented_variable.categories.add(category)




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