# -- STDLIB
import csv
import re
import os
from datetime import datetime


# -- DJANGO
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.detail import DetailView
from django.conf import settings

# views.py
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView, TemplateView
from django.views.generic.edit import FormView

# -- THIRDPARTY
from bs4 import BeautifulSoup
from elasticsearch_dsl import A, Q, Search
import requests


# -- BASEDEQUESTIONS (LOCAL)
from .documents import \
    BindingSurveyDocument
from .forms import CSVUploadForm, CustomAuthenticationForm, XMLUploadForm, SerieForm
from .models import (
    BindingSurveyRepresentedVariable, Category, ConceptualVariable,
    RepresentedVariable, Serie, Survey, Publisher
)
from .utils.csvimportexport import BindingSurveyResource


def admin_required(user):
    return user.is_authenticated and user.is_staff

def normalize_string(value):
    if isinstance(value, str):
        return " ".join(value.split()).strip().lower()
    text = text.replace("…", "...")
    text = re.sub(r"\.{3,}", "...", text) 
    return text.strip()

class BaseUploadView(FormView):
    success_url = reverse_lazy('app:representedvariable_search')

    @transaction.atomic
    def form_valid(self, form):
        data = self.get_data(form)
        question_datas = list(self.convert_data(data))

        try:
            num_records, num_new_surveys, num_new_variables, num_new_bindings = self.process_data(question_datas)
            messages.success(self.request,
                             "Le fichier a été traité avec succès :<br/>"
                             "<ul>"
                             f"<li>{num_records} lignes ont été analysées.</li>"
                             f"<li>{num_new_surveys} nouvelles enquêtes créées.</li>"
                             f"<li>{num_new_variables} nouvelles variables représentées créées.</li>"
                             "</ul>",
                             extra_tags='safe')  # Assurez-vous que le HTML est interprété
            return super().form_valid(form)


        except ValueError as ve:
            # Gérer l'erreur spécifique et rediriger
            messages.error(self.request, f"{ve}", extra_tags="safe")
            return self.form_invalid(form)

        except Exception as e:
            messages.error(self.request, f"Erreur inattendue : {str(e)}", extra_tags="safe")
            return self.form_invalid(form)
            
    def form_invalid(self, form,):
        errors = form.errors.as_data()  # Récupérer les erreurs au format Django
        error_messages = []

        # Ajouter les erreurs du formulaire à la liste des messages
        for field, field_errors in errors.items():
            for error in field_errors:
                error_messages.append(f"{field}: {error}")

        storage = messages.get_messages(self.request)
        for message in storage:
            if message.level_tag == "error":
                error_messages.append(message.message)
        # Si des erreurs spécifiques ont été ajoutées via des exceptions, elles sont déjà dans les messages
        # On peut s'assurer qu'elles sont bien ajoutées à `error_messages`
        messages.error(
            self.request,
            f"Erreurs d'importation :<br/>{'<br/>'.join(error_messages)}",
            extra_tags="safe"
        )

        return super().form_invalid(form)

    def get_data(self, form):
        """Méthode pour obtenir les données du formulaire."""
        pass

    def convert_data(self, content):
        """Méthode pour extraire les données."""
        pass

    def process_data(self, question_datas):
        """Méthode pour traiter les données."""
        pass

    def get_or_create_survey(self, doi, title, serie):
        survey, _ = Survey.objects.get_or_create(external_ref=doi, name=title, serie=serie)
        return survey

    def get_or_create_binding(self, survey, represented_variable, variable_name, universe, notes):
        binding, created = BindingSurveyRepresentedVariable.objects.get_or_create(
            variable_name=variable_name,
            defaults={
                'survey': survey,
                'variable': represented_variable,
                'universe': universe,
                'notes': notes,
            }
        )
        if not created:
            # Mise à jour des champs de la liaison si elle existe déjà
            binding.survey = survey
            binding.variable = represented_variable
            binding.universe = universe
            binding.notes = notes
            binding.save()

        return binding, created

    def check_category(self, category_string, existing_categories):
        csv_categories = self.parse_categories(category_string) if category_string else []
        existing_categories_list = [(category.code, category.category_label) for category in existing_categories.all()]
        return set(csv_categories) == set(existing_categories_list)

    def parse_categories(self, category_string):
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['csv_form'] = CSVUploadForm()
        return context

    def get_data(self, form):
        self.selected_serie = Serie.objects.get(name=form.cleaned_data['series'])
        return form.cleaned_data['csv_file']

    def convert_data(self, content):
        return csv.DictReader(content)

    @transaction.atomic
    def process_data(self, question_datas):
        num_records = 0
        num_new_surveys = 0
        num_new_variables = 0
        num_new_bindings = 0
        error_lines = []

        for line_number, row in enumerate(question_datas, start=1):
            try:
                survey, created_survey = self.get_or_create_survey(row['ddi'], row['title'], self.selected_serie)
                if created_survey:
                    num_new_surveys += 1

                represented_variable, created_variable = self.get_or_create_represented_variable(row, line_number)
                if created_variable:
                    num_new_variables += 1

                binding, created_binding = self.get_or_create_binding(
                    survey, represented_variable,
                    row['variable_name'],
                    row.get('univers', ''),
                    row.get('notes', ''),
                )
                if created_binding:
                    num_new_bindings += 1

                num_records += 1
                
            except ValueError as ve:
                error_lines.append(line_number)
            except Exception as e:
                error_lines.append(line_number)

        if error_lines:
            error_summary = ", ".join(map(str, error_lines))
            raise ValueError(f"Erreurs aux lignes : {error_summary}")

        return num_records, num_new_surveys, num_new_variables, num_new_bindings

    def get_or_create_represented_variable(self, row, line_number):
        """Gérer la création ou la mise à jour d'une variable représentée."""
        name_question = row['question_text']
        category_label = row['category_label']

        var_represented = RepresentedVariable.objects.filter(question_text=name_question)

        if var_represented.exists():
            for var in var_represented:
                if self.check_category(category_label, var.categories):
                    return var, False  # Pas de nouvelle variable créée

            return self.create_new_represented_variable(row, var_represented[0].conceptual_var), True
        else:
            conceptual_var = ConceptualVariable.objects.create()
            return self.create_new_represented_variable(row, conceptual_var), True

    def create_new_represented_variable(self, row, conceptual_var):
        """Créer une nouvelle variable représentée."""
        new_represented_var = RepresentedVariable.objects.create(
            conceptual_var=conceptual_var,
            question_text=row['question_text'],
            internal_label=row['variable_label']
        )
        new_categories = self.create_new_categories(row['category_label'])
        new_represented_var.categories.set(new_categories)
        return new_represented_var

    def create_new_categories(self, csv_category_string):
        """Créer de nouvelles catégories à partir d'une chaîne CSV."""
        categories = []
        if csv_category_string:
            parsed_categories = self.parse_categories(csv_category_string)
            for code, label in parsed_categories:
                category, _ = Category.objects.get_or_create(code=code, category_label=label)
                categories.append(category)
        return categories

    def get_or_create_binding(self, survey, represented_variable, variable_name, universe, notes):
        """Créer ou mettre à jour une liaison entre une enquête et une variable représentée."""
        binding, created = BindingSurveyRepresentedVariable.objects.get_or_create(
            variable_name=variable_name,
            defaults={
                'survey': survey,
                'variable': represented_variable,
                'universe': universe,
                'notes': notes,
            }
        )
        if not created:
            # Mise à jour des champs de la liaison si elle existe déjà
            binding.universe = universe
            binding.notes = notes
            binding.save()

        return binding, created

    def get_or_create_survey(self, doi, title, serie):
        """Créer ou récupérer une enquête."""
        survey, created = Survey.objects.get_or_create(external_ref=doi, name=title, serie=serie)
        return survey, created  # Retourne l'indicateur de création

    def check_category(self, category_string, existing_categories):
        """Vérifier si les catégories correspondent."""
        csv_categories = self.parse_categories(category_string) if category_string else []
        existing_categories_list = [(category.code, category.category_label) for category in existing_categories.all()]
        return set(csv_categories) == set(existing_categories_list)

    def parse_categories(self, category_string):
        """Extraire les catégories d'une chaîne CSV."""
        categories = []
        csv_category_pairs = category_string.split(" | ")
        for pair in csv_category_pairs:
            code, label = pair.split(",", 1)
            categories.append((code.strip(), label.strip()))
        return categories


class ExportQuestionsView(View):
    def get(self, request, *args, **kwargs):
        resource = BindingSurveyResource()
        dataset = resource.export()

        # Créer une réponse HTTP avec le bon type de contenu pour CSV
        response = HttpResponse(dataset.csv, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="questions_export.csv"'
        return response


class XMLUploadView(BaseUploadView):
    template_name = 'upload_xml.html'
    form_class = XMLUploadForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['xml_form'] = XMLUploadForm()
        return context

    def get_data(self, form):
        self.selected_series = form.cleaned_data['series']
        return form.cleaned_data['xml_file']

    def convert_data(self, content):
        soup = BeautifulSoup(content, "xml")
        doi = soup.find("IDNo", attrs={"agency": "DataCite"}).text.strip() if soup.find("IDNo", attrs={
            "agency": "DataCite"}) else soup.find("IDNo").text.strip()
        title = soup.find("titl").text.strip()

        date = None
        date_tag = soup.find("distStmt").find("distDate") if soup.find("distStmt") else None
        if date_tag and date_tag.text.strip():
            try:
                date = datetime.strptime(date_tag.text.strip(), "%Y-%m-%d").date()
            except ValueError:
                date = None
        for line in soup.find_all("var"):
            cat_to_add = " | ".join([','.join([cat.find("catValu").text.strip() if cat.find("catValu") else '',
                                               cat.find("labl").text.strip() if cat.find("labl") else ''])
                                     for cat in line.find_all("catgry")
                                     ])
            question_data = [
                doi,
                title,
                date,
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
        num_new_surveys = 0
        num_new_variables = 0
        num_new_bindings = 0

        for question_data in question_datas:
            try:
                doi, title, date, variable_name, variable_label, question_text, category_label, universe, notes = question_data
                if not doi.startswith('doi:'):
                    raise ValueError(f"Le DOI '{doi}' n'est pas au bon format. Il doit commencer par 'doi:'.")
                # Création ou récupération d'une enquête (Survey)
                survey, created_survey = self.get_or_create_survey(doi, title, self.selected_series, date)
                if created_survey:
                    num_new_surveys += 1

                # Création ou récupération d'une variable représentée (RepresentedVariable)
                represented_variable, created_variable = self.get_or_create_represented_variable(variable_name, question_text, category_label, variable_label)
                if created_variable:
                    num_new_variables += 1

                # Création ou récupération d'une liaison (BindingSurveyRepresentedVariable)
                _, created_binding = self.get_or_create_binding(survey, represented_variable, variable_name, universe, notes)
                if created_binding:
                    num_new_bindings += 1

                num_records += 1
            except ValueError as ve:
                messages.error(self.request, str(ve))
                raise ve

        return num_records, num_new_surveys, num_new_variables, num_new_bindings

    def get_or_create_represented_variable(self, variable_name, question_text, category_label, variable_label):
        var_represented = RepresentedVariable.objects.filter(question_text=question_text)

        if var_represented.exists():
            for var in var_represented:
                if self.check_category(category_label, var.categories):
                    return var, False  # False = pas de nouvelle variable créée
            return self.create_new_represented_variable(variable_name, var_represented[0].conceptual_var, question_text,
                                                        category_label, variable_label), True
        else:
            return self.create_new_represented_variable(variable_name, ConceptualVariable.objects.create(),
                                                        question_text, category_label, variable_label), True

    def create_new_represented_variable(self, variable_name, conceptual_var, question_text, category_label, variable_label):
        new_represented_var = RepresentedVariable.objects.create(
            conceptual_var=conceptual_var,
            question_text=question_text,
            internal_label=variable_label
        )
        self.create_new_categories(category_label, new_represented_var)
        return new_represented_var

    def create_new_categories(self, category_string, represented_variable):
        if category_string:
            parsed_categories = self.parse_categories(category_string)
            for code, label in parsed_categories:
                category, _ = Category.objects.get_or_create(code=code, category_label=label)
                represented_variable.categories.add(category)

    def get_or_create_survey(self, doi, title, serie, date):
        survey, created = Survey.objects.get_or_create(external_ref=doi, name=title, serie=serie)
        if not created and date:
            if survey.date != date:
                survey.date = date
                survey.save()
        elif created and date:
            survey.date = date
            survey.save()
        return survey, created

    # def get_or_create_binding(self, survey, represented_variable, variable_name, universe, notes, serie):
    #     binding, created = BindingSurveyRepresentedVariable.objects.get_or_create(
    #         survey=survey,
    #         variable=represented_variable,
    #         variable_name=variable_name,
    #         notes=notes,
    #         universe=universe
    #     )
    #     return binding, created


# class CombinedUploadView(LoginRequiredMixin, TemplateView):
#     template_name = 'upload_files.html'

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         context['csv_form'] = CSVUploadForm()
#         context['xml_form'] = XMLUploadForm()
#         return context


class RepresentedVariableSearchView(ListView):
    model = RepresentedVariable
    template_name = 'homepage.html'  # Nom du template
    context_object_name = 'variables'  # Nom du contexte utilisé dans le template

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['series'] = Serie.objects.all()
        context['success_message'] = self.request.GET.get('success_message', None)
        context['upload_stats'] = self.request.GET.get('upload_stats', None)
        return context




def search_results(request):
    selected_series = request.GET.getlist('serie')
    selected_studies = request.GET.getlist('survey')

    series = Serie.objects.all()
    studies = Survey.objects.all()

    search_location = request.GET.get('search_location', 'questions')
    context = locals()
    return render(request, 'search_results.html', context)

def apply_highlight(full_text, highlights):
    for highlight in highlights:
        # Remplacer chaque partie du texte original par la version surlignée
        full_text = full_text.replace(highlight.replace("<mark style='background-color: yellow;'>", "").replace("</mark>", ""), highlight)
    return full_text


class SearchResultsDataView(ListView):
    model = BindingSurveyDocument  # Juste à titre indicatif, sans effet direct ici
    context_object_name = 'results'
    paginate_by = 10  # Par défaut

    def get_queryset(self):
        search_value = self.request.GET.get('q', '').strip().lower()
        search_location = self.request.GET.get('search_location', 'questions')
        study_filter = self.request.GET.getlist('study[]', None)
        series_filter = self.request.GET.getlist('series[]', None)

        # Convertir le filtre en liste d'entiers
        study_filter = [int(study_id) for study_id in study_filter if study_id.isdigit()]
        series_filter = [int(serie_id) for serie_id in series_filter if serie_id.isdigit()]

        # Configuration de la recherche Elasticsearch
        search = BindingSurveyDocument.search()

        # Appliquer les filtres de recherche en fonction de `search_location`
        if search_value:
            search = self.apply_search_filters(search, search_value, search_location)

        # Appliquer le surlignage
        search = search.highlight_options(pre_tags=["<mark style='background-color: yellow;'>"],
                                          post_tags=["</mark>"]) \
            .highlight('variable.question_text', fragment_size=10000) \
            .highlight('variable.categories.category_label', fragment_size=10000) \
            .highlight('variable_name', fragment_size=10000)

        # Appliquer le filtre par étude
        if series_filter:
            search = search.filter('terms', **{"survey.serie_id": series_filter})
        if study_filter:
            search = search.filter('terms', **{"survey.id": study_filter})
        

        # Pagination (start et length) depuis DataTables
        start = int(self.request.GET.get('start', 0))
        length = int(self.request.GET.get('length', self.paginate_by))
        if length == -1:
            length = search.count()

        return search[start:start + length].execute()

    def apply_search_filters(self, search, search_value, search_location):
        """Applique des filtres de recherche en fonction du `search_location`."""
        if search_location == 'questions':
            search = search.query(
                'bool',
                should=[
                    {"term": {"variable.question_text.keyword": {"value": search_value, "boost": 10}}},
                    {"match_phrase": {"variable.question_text": {"query": search_value, "boost": 5}}},
                    {"match_phrase_prefix": {"variable.question_text": {"query": search_value, "boost": 1}}}
                ],
                minimum_should_match=1
            )
        elif search_location == 'categories':
            search = search.query('nested', path='variable.categories', query={
                'bool': {
                    'should': [
                        {"term": {"variable.categories.category_label.keyword": {"value": search_value, "boost": 10}}},
                        {"match_phrase": {"variable.categories.category_label": {"query": search_value, "boost": 5}}},
                        {"match_phrase_prefix": {
                            "variable.categories.category_label": {"query": search_value, "boost": 1}}}
                    ],
                    "minimum_should_match": 1
                }
            })
        elif search_location == 'variable_name':
            search = search.query(
                'bool',
                should=[
                    {"term": {"variable_name.keyword": {"value": search_value, "boost": 10}}},
                    {"match_phrase": {"variable_name": {"query": search_value, "boost": 5}}},
                    {"match_phrase_prefix": {"variable_name": {"query": search_value, "boost": 1}}}
                ],
                minimum_should_match=1
            )
        return search

    def format_search_results(self, response, search_location):
        """Formate les résultats de la recherche pour DataTables."""
        data = []
        is_category_search = search_location == 'categories'

        for result in response.hits:
            original_question = getattr(result.variable, 'question_text', "N/A")

            # Logique de surlignage
            highlighted_question = (
                result.meta.highlight['variable.question_text'][0]
                if hasattr(result.meta, 'highlight') and 'variable.question_text' in result.meta.highlight
                else original_question
            )

            category_matched = None
            all_clean_categories = []  # Initialisation de full_cat
            sorted_categories = sorted(result.variable.categories, key=lambda cat: int(cat.code) if cat.code.isdigit() else cat.code)
            # Récupérer la catégorie correspondante
            if search_location == 'categories' and hasattr(result.meta, 'highlight'):
                if 'variable.categories.category_label' in result.meta.highlight:
                    category_highlight = result.meta.highlight['variable.categories.category_label']
                    category_matched = category_highlight[0] if category_highlight else None

            for cat in sorted_categories:
                if category_matched and cat.category_label == remove_html_tags(category_matched):
                    all_clean_categories.append(
                        f"<mark style='background-color: yellow;'>{cat.code} : {cat.category_label}</mark>"
                    )
                else:
                    all_clean_categories.append(f"{cat.code} : {cat.category_label}")

            variable_name = result.variable_name
            if search_location == 'variable_name' and hasattr(result.meta,
                                                              'highlight') and 'variable_name' in result.meta.highlight:
                variable_name = result.meta.highlight['variable_name'][0]
            # Collecte des données formatées
            data.append({
                "id": result.meta.id,
                "variable_name": variable_name,
                "question_text": highlighted_question,
                "survey_name": getattr(result.survey, 'name', "N/A"),
                "notes": getattr(result, 'notes', "N/A"),
                "categories": all_clean_categories,
                "internal_label": result.variable.internal_label,
                "is_category_search": is_category_search,
            })
        return data

    def get(self, request, *args, **kwargs):
        response = self.get_queryset()

        # Total records pour DataTables
        total_records = BindingSurveyDocument.search().count()
        filtered_records = response.hits.total.value

        # Formater les données pour DataTables
        data = self.format_search_results(response, request.GET.get('search_location', 'questions'))

        return JsonResponse({
            "recordsTotal": total_records,
            "recordsFiltered": filtered_records,
            "draw": int(request.GET.get('draw', 1)),
            "data": data
        })


def remove_html_tags(text):
    """Supprime toutes les balises HTML d'une chaîne de caractères."""
    return re.sub(r'<[^>]+>', '', text)


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







class ExportQuestionsCSVView(View):
    def get(self, request, *args, **kwargs):
        selected_series = request.GET.getlist('series')
        selected_surveys = request.GET.getlist('surveys')
        # Créer la réponse CSV
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="questions_export.csv"'

        # Définir les colonnes du CSV
        writer = csv.writer(response)
        writer.writerow(['ddi', 'title', 'variable_name', 'variable_label', 'question_text', 'category_label', 'univers', 'notes'])

        # Récupérer toutes les questions et les informations associées
        questions = BindingSurveyRepresentedVariable.objects.all()

        if selected_series:
            questions = questions.filter(survey__serie__id__in=selected_series)
        if selected_surveys:
            questions = questions.filter(survey__id__in=selected_surveys)

        for question in questions.distinct():
            # Récupérer les liaisons entre les surveys et les variables représentées
            represented_var = question.variable

            if question:
                survey = question.survey  # Récupérer le survey associé à cette variable représentée
                variable_name = question.variable_name
                universe = question.universe
                notes = question.notes
            else:
                survey = None
                variable_name = ''
                universe = ''
                notes = ''

            # Récupérer les catégories associées
            categories = " | ".join ([f"{cat.code},{cat.category_label}" for cat in represented_var.categories.all()])
            
            writer.writerow([
                survey.external_ref if survey else '',  # DOI
                survey.name if survey else '',          # Title
                variable_name,                          # Variable Name
                represented_var.internal_label or '',          # Variable Label
                represented_var.question_text or '',           # Question Text
                categories,                             # Category Label
                universe,                               # Univers
                notes                                   # Notes
            ])

        return response
def export_page(request):
    series = Serie.objects.all()
    surveys = Survey.objects.all()
    context = locals()
    return render(request, 'export_csv.html', context)

class QuestionDetailView(View): 
    def get(self, request, id, *args, **kwargs):
        question = get_object_or_404(BindingSurveyRepresentedVariable, id=id)
        question_represented_var = question.variable
        question_conceptual_var = question_represented_var.conceptual_var
        question_survey = question.survey
        categories = sorted(question.variable.categories.all(), key=lambda x: int(x.code) if x.code.isdigit() else x.code)
        middle_index = len(categories) // 2
        similar_representative_questions = BindingSurveyRepresentedVariable.objects.filter(
            variable=question.variable
        ).exclude(id=question.id)

        similar_conceptual_questions = BindingSurveyRepresentedVariable.objects.filter(
            variable__conceptual_var=question.variable.conceptual_var
        ).exclude(id=question.id).exclude(id__in=similar_representative_questions.values_list('id', flat=True))

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
            "variable_name": similar_question.variable_name,
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
            "variable_name": similar_question.variable_name,
            "question_text": similar_question.variable.question_text,
            "internal_label": similar_question.variable.internal_label or "N/A",
            "survey" : similar_question.survey.name
        })

    return JsonResponse({
        "recordsTotal": len(questions_from_conceptual_variable),
        "recordsFiltered": len(questions_from_conceptual_variable),
        "data": data
    })


class CustomLoginView(LoginView):
    template_name = 'login.html'
    authentication_form = CustomAuthenticationForm
    redirect_authenticated_user = True



class CreateSerie(LoginRequiredMixin, FormView):
    template_name = "create_serie.html"
    form_class = SerieForm
    success_url = reverse_lazy('app:representedvariable_search')

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Série créée avec succès.")
        return super().form_valid(form)



def check_media_root(request):
    # Vérifier si le répertoire MEDIA_ROOT existe
    if not os.path.exists(settings.MEDIA_ROOT):
        return JsonResponse({"error": "MEDIA_ROOT directory does not exist."})

    # Parcourir les fichiers et dossiers dans MEDIA_ROOT
    media_files_info = []
    for root, dirs, files in os.walk(settings.MEDIA_ROOT):
        for name in files:
            file_path = os.path.join(root, name)
            relative_path = os.path.relpath(file_path, settings.MEDIA_ROOT)

            # Tenter de construire l'URL de l'image et vérifier si l'URL est accessible
            file_url = os.path.join(settings.MEDIA_URL, relative_path).replace("\\", "/")
            file_exists = check_file_access(file_url)

            # Obtenir les informations sur le fichier
            file_info = {
                "name": name,
                "relative_path": relative_path,
                "size": os.path.getsize(file_path),  # Taille en octets
                "last_modified": datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat(),
                "url": file_url,
                "accessible": file_exists,
            }
            media_files_info.append(file_info)

    return JsonResponse({
        "MEDIA_ROOT": str(settings.MEDIA_ROOT),
        "MEDIA_URL": settings.MEDIA_URL,
        "file_count": len(media_files_info),
        "files": media_files_info,
    })


def check_file_access(file_url):
    """
    Fonction qui essaie de faire une requête HTTP GET pour vérifier si l'URL du fichier est accessible.
    Retourne True si le fichier est accessible, sinon False.
    """


    # Construire l'URL complète (en prenant en compte la configuration du domaine et du path)
    # Ici, on assume que l'URL du fichier est accessible via un domaine public
    full_url = f"http://{settings.ALLOWED_HOSTS[0]}{file_url}"

    try:
        response = requests.get(full_url)
        # Si le code de réponse est 200, cela signifie que le fichier est accessible
        return response.status_code == 200
    except requests.exceptions.RequestException:
        # Si une exception se produit, on considère que le fichier n'est pas accessible
        return False

@csrf_exempt
def check_duplicates(request):
    if request.method == 'POST':
        # Récupérer soit le fichier CSV, soit le fichier XML
        file = request.FILES.get('csv_file') or request.FILES.get('xml_file')
        
        if not file:
            return JsonResponse({'error': 'Aucun fichier fourni'}, status=400)
        decoded_file = file.read().decode('utf-8', errors='replace').splitlines()
        
        # Vérifier si c'est un fichier XML
        if file.name.endswith('.xml'):
            soup = BeautifulSoup("\n".join(decoded_file), 'xml')
            existing_variables = []
            variable_survey_id = soup.find("IDNo", attrs={"agency": "DataCite"}).text.strip() if soup.find("IDNo", attrs={
            "agency": "DataCite"}) else soup.find("IDNo").text.strip()
            for var in soup.find_all('var'):
                variable_name = var.get('name', '').strip()
                existing_bindings = BindingSurveyRepresentedVariable.objects.filter(variable_name=variable_name, survey__external_ref=variable_survey_id)
                if existing_bindings.exists():
                    existing_variables.append(variable_name)

        # Vérifier si c'est un fichier CSV
        elif file.name.endswith('.csv'):
            reader = csv.DictReader(decoded_file)
            existing_variables = []
            for row in reader:
                variable_name = row['variable_name']
                variable_survey_id = row['ddi']
                existing_bindings = BindingSurveyRepresentedVariable.objects.filter(variable_name=variable_name, survey__external_ref=variable_survey_id)
                if existing_bindings.exists():
                    existing_variables.append(variable_name)
        
        else:
            return JsonResponse({'error': 'Format de fichier non supporté'}, status=400)
        if existing_variables:
            return JsonResponse({'status': 'exists', 'existing_variables': existing_variables})
        else:
            return JsonResponse({'status': 'no_duplicates'})

    return JsonResponse({'error': 'Requête invalide'}, status=400)


class SerieSurveysView(View):
    def get(self, request, serie_id):
        serie = get_object_or_404(Serie, id=serie_id)
        surveys = Survey.objects.filter(serie=serie)
        return render(request, 'serie_surveys.html', {'serie': serie, 'surveys': surveys})



def get_surveys_by_series(request):
    series_ids = request.GET.get('series_ids')
    if series_ids:
        series_ids = [int(id) for id in series_ids.split(',')]
        surveys = Survey.objects.filter(serie__id__in=series_ids)
    else:
        surveys = Survey.objects.all()
    

    surveys_data = [{'id': survey.id, 'name': survey.name} for survey in surveys]
    return JsonResponse({'surveys': surveys_data})

def create_publisher(request):
    if request.method == "POST":
        name = request.POST.get('name')
        if name:
            Publisher.objects.get_or_create(name=name)
            return JsonResponse({"success": True, "message": "Éditeur ajouté avec succès."})
        return JsonResponse({"success": False, "message": "Le nom de l'éditeur est requis."})
    return JsonResponse({"success": False, "message": "Requête invalide."})

def get_publishers(request):
    publishers = Publisher.objects.all().values("id", "name")
    return JsonResponse({"publishers": list(publishers)})