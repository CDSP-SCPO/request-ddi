# -- STDLIB
import csv
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from html import unescape

# -- DJANGO
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.db import IntegrityError, transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import Signal, receiver
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
# views.py
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView, TemplateView
from django.views.generic.edit import FormView

# -- THIRDPARTY
import requests
from bs4 import BeautifulSoup
from elasticsearch_dsl import A, Q, Search

# -- BASEDEQUESTIONS (LOCAL)
from .documents import BindingSurveyDocument
from .forms import (
    CSVUploadForm, CSVUploadFormCollection, CustomAuthenticationForm,
    XMLUploadForm,
)
from .models import (
    BindingSurveyRepresentedVariable, Category, Collection, ConceptualVariable,
    Distributor, RepresentedVariable, Subcollection, Survey,
)
from .signals import data_imported
from .utils.normalize_string import (
    normalize_string_for_comparison, normalize_string_for_database,
)

from .utils.sort import alphanum_key


class BaseUploadView(FormView):
    success_url = reverse_lazy('app:representedvariable_search')

    def handle_error(self, message, form=None):
        messages.error(self.request, message, extra_tags="safe")
        if form:
            return self.form_invalid(form)
        return None

    @transaction.atomic
    def form_valid(self, form):
        self.errors = []  # Initialiser self.errors comme une liste vide
        data = self.get_data(form)
        question_datas = list(self.convert_data(data))

        if self.errors:
            return self.form_invalid(form)

        try:
            num_records, num_new_surveys, num_new_variables, num_new_bindings = self.process_data(question_datas)

            # Vérifier s'il y a des erreurs après l'appel à process_data
            if self.errors:
                return self.form_invalid(form)

            messages.success(self.request,
                             "Le fichier a été traité avec succès :<br/>"
                             "<ul>"
                             f"<li>{num_records} lignes ont été analysées.</li>"
                             f"<li>{num_new_surveys} nouvelles enquêtes créées.</li>"
                             f"<li>{num_new_variables} nouvelles variables représentées créées.</li>"
                             "</ul>",
                             extra_tags='safe')
            return super().form_valid(form)

        except ValueError as ve:
            return self.handle_error(f"{ve}", form)

        except Exception as e:
            return self.handle_error(f"Erreur inattendue : {str(e)}", form)

    def form_invalid(self, form):
        errors = form.errors.as_data()  # Récupérer les erreurs au format Django
        error_messages = []

        # Ajouter les erreurs du formulaire à la liste des messages
        for field, field_errors in errors.items():
            for error in field_errors:
                # Nettoyer le message d'erreur pour enlever les crochets
                cleaned_error = str(error).strip("[]").strip("'")
                error_messages.append(cleaned_error)

        storage = messages.get_messages(self.request)
        for message in storage:
            if message.level_tag == "error":
                error_messages.append(message.message)

        if error_messages:
            messages.error(
                self.request,
                f"{'<br/>'.join(error_messages)}",
                extra_tags="safe"
            )

        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['errors'] = getattr(self, 'errors', [])
        self.add_form_to_context(context)
        return context

    def add_form_to_context(self, context):
        """Ajouter le formulaire spécifique au contexte."""
        raise NotImplementedError("Cette méthode doit être implémentée dans les sous-classes.")

    def get_data(self, form):
        """Méthode pour obtenir les données du formulaire."""
        pass

    def convert_data(self, content):
        """Méthode pour extraire les données."""
        pass

    def process_data(self, question_datas):
        """Méthode pour traiter les données."""
        pass

    def get_or_create_survey(self):
        pass

    @transaction.atomic
    def get_or_create_binding(self, survey, represented_variable, variable_name, universe, notes):
        try:
            binding, created = BindingSurveyRepresentedVariable.objects.get_or_create(
                variable_name=variable_name,
                survey=survey,
                variable = represented_variable,
                defaults={
                    'survey': survey,
                    'variable': represented_variable,
                    'universe': universe,
                    'notes': notes,
                }
            )
        except BindingSurveyRepresentedVariable.MultipleObjectsReturned:
            bindings = BindingSurveyRepresentedVariable.objects.filter(variable_name=variable_name)
            if all(binding.variable == represented_variable for binding in bindings):
                binding = bindings.first()
                created = False
            else:
                raise ValueError(
                    "Multiple bindings found with the same variable_name but different represented_variable.")

        if not created:
            # Mise à jour des champs de la liaison si elle existe déjà
            binding.survey = survey
            binding.variable = represented_variable
            binding.universe = universe
            binding.notes = notes
            binding.save()

        return binding, created

    def check_category(self, category_string, existing_categories):

        csv_categories = [(code, normalize_string_for_comparison(normalize_string_for_database(label))) for code, label
                          in self.parse_categories(category_string)] if category_string else []
        existing_categories_list = [(category.code, normalize_string_for_comparison(category.category_label)) for
                                    category in existing_categories.all()]

        return set(csv_categories) == set(existing_categories_list)

    def parse_categories(self, category_string):
        categories = []
        csv_category_pairs = category_string.split(" | ")
        for pair in csv_category_pairs:
            code, label = pair.split(",", 1)
            categories.append((code.strip(), label.strip()))
        return categories

    @transaction.atomic
    def create_new_categories(self, category_string):
        categories = []
        if category_string:
            parsed_categories = self.parse_categories(category_string)
            for code, label in parsed_categories:
                category, _ = Category.objects.get_or_create(code=code,
                                                             category_label=normalize_string_for_database(label))
                categories.append(category)
        return categories

    @transaction.atomic
    def create_new_represented_variable(self, conceptual_var, name_question_normalized, category_label,
                                        variable_label, is_unique: bool = False):
        new_represented_var = RepresentedVariable.objects.create(
            conceptual_var=conceptual_var,
            question_text=name_question_normalized,
            internal_label=variable_label,
            is_unique=is_unique,
        )
        new_categories = self.create_new_categories(category_label)
        new_represented_var.categories.set(new_categories)
        return new_represented_var

    @transaction.atomic
    def get_or_create_represented_variable(self, variable_name, question_text, category_label, variable_label):
        """Gérer la création ou la mise à jour d'une variable représentée."""
        name_question_for_database = normalize_string_for_database(question_text)
        name_question_for_comparison = normalize_string_for_comparison(name_question_for_database)

        cleaned_questions = RepresentedVariable.get_cleaned_question_texts()

        if name_question_for_comparison :
            if name_question_for_comparison in cleaned_questions:
                var_represented = RepresentedVariable.objects.filter(
                    question_text=cleaned_questions[name_question_for_comparison].question_text
                )
                for var in var_represented:
                    if self.check_category(category_label, var.categories):
                        return var, False
                return self.create_new_represented_variable(var_represented[0].conceptual_var,
                                                            name_question_for_database, category_label,
                                                            variable_label), True
            else:
                conceptual_var = ConceptualVariable.objects.create()
                return self.create_new_represented_variable(conceptual_var, name_question_for_database,
                                                            category_label,
                                                            variable_label), True
        else:
            conceptual_var = ConceptualVariable.objects.create(is_unique=True)
            return self.create_new_represented_variable(conceptual_var, name_question_for_database,
                                                        category_label,
                                                        variable_label), True


class CSVUploadView(BaseUploadView):
    template_name = 'upload_csv.html'
    form_class = CSVUploadForm

    def add_form_to_context(self, context):
        context['csv_form'] = CSVUploadForm()

    def get_data(self, form):
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
                with transaction.atomic():
                    survey = Survey.objects.get(external_ref=row["doi"])

                    represented_variable, created_variable = self.get_or_create_represented_variable(
                        row["variable_name"], row["question_text"], row["category_label"], row["variable_label"])
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

            except Survey.DoesNotExist:
                error_message = f"Ligne {line_number}: DOI '{row['doi']}' non trouvé dans la base de données."
                error_lines.append(error_message)
            except ValueError as ve:
                error_message = f"Ligne {line_number}: Erreur de format de date : {ve}"
                error_lines.append(error_message)
            except Exception as e:
                error_message = f"Ligne {line_number}: Erreur inattendue : {e}"
                error_lines.append(error_message)

        if error_lines:
            error_summary = "<br/>".join(error_lines)
            raise ValueError(f"Erreurs rencontrées :<br/> {error_summary}")

        return num_records, num_new_surveys, num_new_variables, num_new_bindings


class XMLUploadView(BaseUploadView):
    template_name = 'upload_xml.html'
    form_class = XMLUploadForm


    def add_form_to_context(self, context):
        context['xml_form'] = XMLUploadForm()

    def get_data(self, form):
        files = self.request.FILES.getlist('xml_file')
        self.errors = []
        return files

    def convert_data(self, files):
        results = []
        seen_invalid_dois = set()
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_file = {executor.submit(self.parse_xml_file, file, seen_invalid_dois): file for file in files}
            for future in as_completed(future_to_file):
                file = future_to_file[future]
                try:
                    result = future.result()
                    if result:
                        results.extend(result)
                except Exception as e:
                    self.errors.append(f"Erreur lors de la lecture du fichier {file.name}: {str(e)}")
        return results


    def parse_xml_file(self, file, seen_invalid_dois):
        """Parser un fichier XML et retourner ses données."""
        start_time = datetime.now()  # Début du parsing
        try:

            file.seek(0)
            content = file.read().decode('utf-8')
            soup = BeautifulSoup(content, "xml")

            # Récupérer DOI et titre
            doi = soup.find("IDNo", attrs={"agency": "DataCite"}).text.strip() if soup.find("IDNo", attrs={
                "agency": "DataCite"}) else soup.find("IDNo").text.strip()
            if not doi.startswith("doi:"):
                if doi not in seen_invalid_dois:
                    seen_invalid_dois.add(doi)
                    self.errors.append(
                        f"<strong>{file.name}</strong> : DOI invalide '<strong>{doi}</strong>' (doit commencer par 'doi:').")
                return None

            data = []
            for line in soup.find_all("var"):
                categories = " | ".join([
                    ','.join([cat.find("catValu").text.strip() if cat.find("catValu") else '',
                              cat.find("labl").text.strip() if cat.find("labl") else ''])
                    for cat in line.find_all("catgry")
                ])

                data.append([
                    doi,
                    line["name"].strip(),
                    line.find("labl").text.strip() if line.find("labl") else "",
                    line.find("qstnLit").text.strip() if line.find("qstnLit") else "",
                    categories,  # Catégories
                    line.find("universe").text.strip() if line.find("universe") else "",
                    line.find("notes").text.strip() if line.find("notes") else "",
                ])

            end_time = datetime.now()  # Fin du parsing
            return data

        except Exception as e:
            print(f"Erreur lors du parsing du fichier {file.name}: {str(e)}")
            return None

    def process_data(self, question_datas):
        num_records = 0
        num_new_surveys = 0
        num_new_variables = 0
        num_new_bindings = 0
        error_files = []

        # Utiliser un dictionnaire pour regrouper les données par DOI
        data_by_doi = {}
        for question_data in question_datas:
            doi = question_data[0]
            if doi not in data_by_doi:
                data_by_doi[doi] = []
            data_by_doi[doi].append(question_data)

        for doi, questions in data_by_doi.items():
            try:
                start_time = datetime.now()  # Début du traitement du DOI

                survey = Survey.objects.get(external_ref=doi)

                for question_data in questions:
                    variable_name, variable_label, question_text, category_label, universe, notes = question_data[1:]

                    represented_variable, created_variable = self.get_or_create_represented_variable(
                        variable_name, question_text, category_label, variable_label
                    )

                    if created_variable:
                        num_new_variables += 1

                    binding, created_binding = self.get_or_create_binding(
                        survey, represented_variable, variable_name, universe, notes
                    )

                    if created_binding:
                        num_new_bindings += 1

                    data_imported.send(sender=self.__class__, instance=binding)

                    num_records += 1

                end_time = datetime.now()  # Fin du traitement du DOI

            except Survey.DoesNotExist:
                error_message = f"DOI '{doi}' non trouvé dans la base de données pour le fichier."
                error_files.append(error_message)
                print(error_message)
            except ValueError as ve:
                error_message = f"DOI '{doi}': Erreur de valeur : {ve}"
                error_files.append(error_message)
                print(error_message)
            except Exception as e:
                error_message = f"DOI '{doi}': Erreur inattendue : {e}"
                error_files.append(error_message)
                print(error_message)

        # Si des erreurs ont été rencontrées, on les affiche
        if error_files:
            self.errors = error_files
            error_summary = "<br/>".join(error_files)
            raise ValueError(f"Erreurs rencontrées :<br/> {error_summary}")

        return num_records, num_new_surveys, num_new_variables, num_new_bindings


class RepresentedVariableSearchView(ListView):
    model = RepresentedVariable
    template_name = 'homepage.html'  # Nom du template
    context_object_name = 'variables'  # Nom du contexte utilisé dans le template

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['collections'] = Collection.objects.all()
        context['success_message'] = self.request.GET.get('success_message', None)
        context['upload_stats'] = self.request.GET.get('upload_stats', None)
        return context


class SearchResultsDataView(ListView):
    model = BindingSurveyDocument
    context_object_name = 'results'
    paginate_by = 10

    @csrf_exempt
    def dispatch(self, *args, **kwargs):
        if 'search_location' not in self.request.session or not self.request.session['search_location']:
            self.request.session['search_location'] = ['questions', 'categories', 'variable_name', 'internal_label']
        return super().dispatch(*args, **kwargs)

    def build_filtered_search(self):
        search_value = self.request.POST.get('q', '').strip().lower()
        search_value = unescape(search_value)

        search_locations = self.request.POST.getlist('search_location[]',
                                                     ['questions', 'categories', 'variable_name', 'internal_label'])
        survey_filter = self.request.POST.getlist('survey[]', None)
        subcollection_filter = self.request.POST.getlist('sub_collections[]', None)
        collections_filter = self.request.POST.getlist('collections[]', None)
        years = self.request.POST.getlist('years[]', [])

        survey_filter = [int(survey_id) for survey_id in survey_filter if survey_id.isdigit()]
        subcollection_filter = [int(subcollection_id) for subcollection_id in subcollection_filter if
                                subcollection_id.isdigit()]
        collections_filter = [int(collection_id) for collection_id in collections_filter if collection_id.isdigit()]
        years = [int(year) for year in years if year.isdigit()]

        search = BindingSurveyDocument.search()

        if search_value:
            search = self.apply_search_filters(search, search_value, search_locations)

        search = search.highlight_options(pre_tags=["<mark style='background-color: yellow;'>"],
                                          post_tags=["</mark>"], number_of_fragments=0, fragment_size=10000) \
            .highlight('variable.question_text', fragment_size=10000) \
            .highlight('variable.categories.category_label', fragment_size=10000) \
            .highlight('variable_name', fragment_size=10000) \
            .highlight('variable.internal_label', fragment_size=10000)

        if survey_filter:
            search = search.filter('terms', **{"survey.id": survey_filter})
        elif subcollection_filter:
            search = search.filter('terms', **{"survey.subcollection.id": subcollection_filter})
        elif collections_filter:
            search = search.filter('terms', **{"survey.subcollection.collection_id": collections_filter})

        if years:
            # Construire des filtres de range pour chaque année sélectionnée
            year_filters = [
                Q('range', **{
                    "survey.start_date": {
                        "gte": f"{year}-01-01",
                        "lt": f"{year + 1}-01-01"
                    }
                })
                for year in years
            ]
            # Appliquer les filtres avec un bool should pour les combiner
            search = search.query('bool', should=year_filters, minimum_should_match=1)

        return search

    def get_queryset(self):
        search = self.build_filtered_search()
        start = int(self.request.POST.get('start', 0))
        limit = int(self.request.POST.get('limit', self.paginate_by))

        response = search[start:start + limit].execute()
        return search[start:start + limit].execute()

    def apply_search_filters(self, search, search_value, search_locations):
        queries = []
        terms = search_value.split()

        for search_location in search_locations:
            if search_location == 'questions':
                queries.append(
                    {"match_phrase_prefix": {"variable.question_text": {"query": search_value, "boost": 10}}}
                )
                queries.append(
                    {"match": {"variable.question_text": {"query": search_value, "operator": "and", "boost": 5}}}
                )
                for term in terms:
                    queries.append(
                        {"match": {"variable.question_text": {"query": term, "operator": "or", "boost": 1}}}
                    )
            elif search_location == 'categories':
                queries.append(
                    {"nested": {
                        "path": "variable.categories",
                        "query": {
                            "bool": {
                                "should": [
                                    {"match_phrase_prefix": {
                                        "variable.categories.category_label": {"query": search_value, "boost": 10}}},
                                    {"match": {
                                        "variable.categories.category_label": {"query": search_value, "operator": "and",
                                                                               "boost": 5}}},
                                    *[
                                        {"match": {
                                            "variable.categories.category_label": {"query": term, "operator": "or",
                                                                                   "boost": 1}}}
                                        for term in terms
                                    ]
                                ],
                                "minimum_should_match": 1
                            }
                        }
                    }}
                )
            elif search_location == 'variable_name':
                queries.append(
                    {"match_phrase_prefix": {
                        "variable_name": {"query": search_value, "boost": 10}
                    }}
                )
                for term in terms:
                    queries.append(
                    {"match": {"variable_name": {"query": search_value, "operator": "and", "boost": 5}}}
                    )
            elif search_location == 'internal_label':
                queries.append(
                    {"match_phrase_prefix": {"variable.internal_label": {"query": search_value, "boost": 10}}}
                )
                queries.append(
                    {"match": {"variable.internal_label": {"query": search_value, "operator": "and", "boost": 5}}}
                )
                for term in terms:
                    queries.append(
                        {"match": {"variable.internal_label": {"query": term, "operator": "or", "boost": 1}}}
                    )


        if queries:
            search = search.query(
                'bool',
                should=queries,
                minimum_should_match=1
            )
        return search

    def format_search_results(self, response, search_locations):
        data = []
        is_category_search = 'categories' in search_locations

        for result in response.hits:
            original_question = getattr(result.variable, 'question_text', "N/A")

            highlighted_question = (
                result.meta.highlight['variable.question_text'][0]
                if hasattr(result.meta, 'highlight') and 'variable.question_text' in result.meta.highlight
                else original_question
            )

            category_matched = None
            all_clean_categories = []
            sorted_categories = sorted(result.variable.categories, key=lambda cat: (
                int(cat.code) if cat.code.isdigit() else float('inf'), cat.code))

            if 'categories' in search_locations and hasattr(result.meta, 'highlight'):
                if 'variable.categories.category_label' in result.meta.highlight:
                    category_highlight = result.meta.highlight['variable.categories.category_label']
                    category_matched = category_highlight[0] if category_highlight else None

            for cat in sorted_categories:
                if category_matched and cat.category_label == remove_html_tags(category_matched):
                    all_clean_categories.append(
                         f"<tr><td class='code-cell'><mark style='background-color: yellow;'>{cat.code}</mark></td><td class='text-cell'><mark style='background-color: yellow;'>{cat.category_label}</mark></td></tr>"
                    )
                else:
                    all_clean_categories.append(
                        f"<tr><td class='code-cell'>{cat.code}</td><td class='text-cell'>{cat.category_label}</td></tr>"
                    )

            variable_name = result.variable_name
            if 'variable_name' in search_locations and hasattr(result.meta,
                                                               'highlight') and 'variable_name' in result.meta.highlight:
                variable_name = result.meta.highlight['variable_name'][0]

            internal_label = result.variable.internal_label
            if 'internal_label' in search_locations and hasattr(result.meta,
                                                                'highlight') and 'variable.internal_label' in result.meta.highlight:
                internal_label = result.meta.highlight['variable.internal_label'][0]

            survey_doi = getattr(result.survey, 'external_ref', "N/A")

            data.append({
                "id": result.meta.id,
                "variable_name": variable_name,
                "question_text": highlighted_question,
                "survey_name": getattr(result.survey, 'name', "N/A"),
                "notes": getattr(result, 'notes', "N/A"),
                "categories": "<table class='styled-table'>" + "".join(all_clean_categories) + "</table>",
                "internal_label": internal_label,
                "is_category_search": is_category_search,
                "survey_doi": survey_doi
            })
        return data

    def post(self, request, *args, **kwargs):
        response = self.get_queryset()

        total_records = self.build_filtered_search().count()
        filtered_records = response.hits.total.value
        data = self.format_search_results(response, request.POST.getlist('search_location[]', ['questions', 'categories', 'variable_name', 'internal_label']))

        return JsonResponse({
            "recordsTotal": total_records,
            "recordsFiltered": filtered_records,
            "draw": int(request.POST.get('draw', 1)),
            "data": data
        })


class CSVUploadViewCollection(FormView):
    template_name = 'upload_csv_collection.html'
    form_class = CSVUploadFormCollection

    def form_valid(self, form):
        try:
            data = self.get_data(form)
            delimiter = form.cleaned_data['delimiter']
            survey_datas = list(self.convert_data(data, delimiter))
            self.process_data(survey_datas)
            return JsonResponse({'status': 'success', 'message': 'Le fichier CSV a été importé avec succès.'})
        except forms.ValidationError as ve:
            print(ve.messages)
            return JsonResponse({'status': 'error', 'message': ve.messages})
        except IntegrityError as ie:
            doi = self.extract_doi_from_error(str(ie))
            if 'unique constraint' in str(ie):
                return JsonResponse({'status': 'error',
                                     'message': f"Une enquête avec le DOI {doi} existe déjà dans la base de données."})
        except ValueError as ve:
            return JsonResponse({'status': 'error', 'message': str(ve)})
        except Exception as e:
            return JsonResponse(
                {'status': 'error', 'message': f"Erreur lors de l'importation du fichier CSV : {str(e)}"})

    def form_invalid(self, form):
        errors = form.errors.as_json()
        return JsonResponse({'status': 'error', 'message': 'Le formulaire est invalide.', 'errors': errors})

    def get_data(self, form):
        # Utilisez les données décodées du formulaire
        return form.cleaned_data['decoded_csv']

    def convert_data(self, content, delimiter):
        # Utilisez le délimiteur détecté dans le formulaire
        reader = csv.DictReader(content, delimiter=delimiter)
        return reader

    def extract_doi_from_error(self, error_message):
        # Extraire le DOI du message d'erreur
        # -- STDLIB
        import re
        match = re.search(r'\(external_ref\)=\((.*?)\)', error_message)
        return match.group(1) if match else 'inconnu'

    @transaction.atomic
    def process_data(self, survey_datas):
        for line_number, row in enumerate(survey_datas, start=1):
            distributor_name = row['distributor']
            distributor, created = Distributor.objects.get_or_create(name=distributor_name)

            collection_name = row['collection']
            collection, created = Collection.objects.get_or_create(name=collection_name, distributor=distributor)

            subcollection_name = row['sous-collection']
            subcollection, created = Subcollection.objects.get_or_create(name=subcollection_name, collection=collection)

            survey_doi = row['doi']
            if not survey_doi.startswith("doi:"):
                raise ValueError(f"Le DOI à la ligne {line_number} n'est pas dans le bon format : {survey_doi}")

            survey_name = row['title']
            survey_language = row['xml_lang']
            survey_author = row['author']
            survey_producer = row['producer']
            survey_start_date = row['start_date']
            survey_geographic_coverage = row['geographic_coverage']
            survey_geographic_unit = row['geographic_unit']
            survey_unit_of_analysis = row['unit_of_analysis']
            survey_contact = row['contact']
            survey_date_last_version = row['date_last_version']

            # Conversion de survey_start_date en objet date (année uniquement)
            if survey_start_date:
                try:
                    # Tente de convertir la date au format "YYYY"
                    survey_start_date = datetime.strptime(survey_start_date, '%Y').date()
                except ValueError:
                    try:
                        # Si ça échoue, tente de convertir la date au format "YYYY-MM-DD"
                        survey_start_date = datetime.strptime(survey_start_date, '%Y-%m-%d').date()
                    except ValueError:
                        raise ValueError(
                            f"L'année de début à la ligne {line_number} n'est pas valide : {survey_start_date}")
            else:
                survey_start_date = None

            # Vérification et formatage de survey_date_last_version
            if survey_date_last_version:
                if len(survey_date_last_version) == 7:  # Format YYYY-MM
                    survey_date_last_version += '-01'
                try:
                    survey_date_last_version = datetime.strptime(survey_date_last_version, '%Y-%m-%d').date()
                except ValueError:
                    raise ValueError(
                        f"La date de la dernière version à la ligne {line_number} n'est pas valide : {survey_date_last_version}")
            else:
                survey_date_last_version = None
            Survey.objects.get_or_create(
                external_ref=survey_doi,
                name=survey_name,
                subcollection=subcollection,
                language=survey_language,
                author=survey_author,
                producer=survey_producer,
                start_date=survey_start_date,
                geographic_coverage=survey_geographic_coverage,
                geographic_unit=survey_geographic_unit,
                unit_of_analysis=survey_unit_of_analysis,
                contact=survey_contact,
                date_last_version=survey_date_last_version,
            )


class ExportQuestionsCSVView(View):
    def get(self, request, *args, **kwargs):
        selected_ids = request.GET.getlist('ids')
        # Créer la réponse CSV
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="questions_export.csv"'

        # Définir les colonnes du CSV
        writer = csv.writer(response)
        writer.writerow(
            ['doi', 'title', 'variable_name', 'variable_label', 'question_text', 'category_label', 'univers', 'notes'])

        # Récupérer toutes les questions et les informations associées
        questions = BindingSurveyRepresentedVariable.objects.all()

        if selected_ids:
            questions = questions.filter(id__in=selected_ids)

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
            categories = " | ".join([f"{cat.code},{cat.category_label}" for cat in represented_var.categories.all()])

            writer.writerow([
                survey.external_ref if survey else '',  # DOI
                survey.name if survey else '',  # Title
                variable_name,  # Variable Name
                represented_var.internal_label or '',  # Variable Label
                represented_var.question_text or '',  # Question Text
                categories,  # Category Label
                universe,  # Univers
                notes  # Notes
            ])

        return response


class QuestionDetailView(View):
    def get(self, request, id, *args, **kwargs):
        question = get_object_or_404(BindingSurveyRepresentedVariable, id=id)
        question_represented_var = question.variable
        question_conceptual_var = question_represented_var.conceptual_var
        question_survey = question.survey

        # Tri des catégories
        categories = sorted(
            question.variable.categories.all(),
            key=lambda x: (int(x.code) if x.code.isdigit() else float('inf'), x.code)
        )

        similar_representative_questions = BindingSurveyRepresentedVariable.objects.filter(
            variable=question.variable,
            variable__is_unique=False
        ).exclude(id=question.id)

        similar_conceptual_questions = BindingSurveyRepresentedVariable.objects.filter(
            variable__conceptual_var=question.variable.conceptual_var,
            variable__conceptual_var__is_unique=False
        ).exclude(
            id=question.id
        ).exclude(
            id__in=similar_representative_questions.values_list('id', flat=True)
        )

        context = locals()
        return render(request, 'question_detail.html', context)


class CustomLoginView(LoginView):
    template_name = 'login.html'
    authentication_form = CustomAuthenticationForm
    redirect_authenticated_user = True



def search_results(request):
    selected_surveys = request.GET.getlist('survey')
    selected_sub_collection = request.GET.getlist('subcollection')
    selected_collection = request.GET.getlist('collection')
    search_locations = request.GET.getlist('search_location')
    search_query = request.GET.get('q', '')

    # Initialiser search_location avec toutes les options si elle est vide
    if not search_locations:
        search_locations = ['questions', 'categories', 'variable_name', 'internal_label']

    request.session['selected_surveys'] = selected_surveys
    request.session['selected_sub_collection'] = selected_sub_collection
    request.session['selected_collection'] = selected_collection
    request.session['search_location'] = search_locations

    collections = Collection.objects.all().order_by("name")
    subcollections = Subcollection.objects.all().order_by("name")
    surveys = Survey.objects.all().order_by("name")

    years = Survey.objects.values_list('start_date', flat=True).distinct()
    years = [year.year for year in years if year is not None]
    years.sort()

    decades = {}
    for year in years:
        decade = (year // 10) * 10
        if decade not in decades:
            decades[decade] = []
        decades[decade].append(year)

    context = {
        'collections': collections,
        'subcollections': subcollections,
        'surveys': surveys,
        'search_location': search_locations,
        'selected_surveys': selected_surveys,
        'selected_sub_collection': selected_sub_collection,
        'selected_collection': selected_collection,
        'show_search_bar': True,
        'decades': decades,
        'search_query': search_query,
    }
    return render(request, 'search_results.html', context)


def similar_representative_variable_questions(request, question_id):
    question = get_object_or_404(BindingSurveyRepresentedVariable, id=question_id)

    rep_variable = question.variable
    questions_from_rep_variable = BindingSurveyRepresentedVariable.objects.filter(variable=rep_variable).exclude(
        id=question_id)

    data = []
    for similar_question in questions_from_rep_variable:
        data.append({
            "id": similar_question.id,
            "variable_name": similar_question.variable_name,
            "question_text": similar_question.variable.question_text,
            "internal_label": similar_question.variable.internal_label or "N/A",
            "survey": similar_question.survey.name
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

    questions_from_conceptual_variable = BindingSurveyRepresentedVariable.objects.filter(
        variable__conceptual_var=conceptual_variable).exclude(id=question_id)

    data = []
    for similar_question in questions_from_conceptual_variable:
        data.append({
            "id": similar_question.id,
            "variable_name": similar_question.variable_name,
            "question_text": similar_question.variable.question_text,
            "internal_label": similar_question.variable.internal_label or "N/A",
            "survey": similar_question.survey.name
        })

    return JsonResponse({
        "recordsTotal": len(questions_from_conceptual_variable),
        "recordsFiltered": len(questions_from_conceptual_variable),
        "data": data
    })


def remove_html_tags(text):
    """Supprime toutes les balises HTML d'une chaîne de caractères."""
    return re.sub(r'<[^>]+>', '', text)


def export_page(request):
    collections = Collection.objects.all()
    surveys = Survey.objects.all()
    context = locals()
    return render(request, 'export_csv.html', context)


def admin_required(user):
    return user.is_authenticated and user.is_staff


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
            variable_survey_id = soup.find("IDNo", attrs={"agency": "DataCite"}).text.strip() if soup.find("IDNo",
                                                                                                           attrs={
                                                                                                               "agency": "DataCite"}) else soup.find(
                "IDNo").text.strip()
            for var in soup.find_all('var'):
                variable_name = var.get('name', '').strip()
                existing_bindings = BindingSurveyRepresentedVariable.objects.filter(variable_name=variable_name,
                                                                                    survey__external_ref=variable_survey_id)
                if existing_bindings.exists():
                    existing_variables.append(variable_name)

        # Vérifier si c'est un fichier CSV
        elif file.name.endswith('.csv'):
            reader = csv.DictReader(decoded_file)
            existing_variables = []
            for row in reader:
                variable_name = row['variable_name']
                variable_survey_id = row['doi']
                existing_bindings = BindingSurveyRepresentedVariable.objects.filter(variable_name=variable_name,
                                                                                    survey__external_ref=variable_survey_id)
                if existing_bindings.exists():
                    existing_variables.append(variable_name)

        else:
            return JsonResponse({'error': 'Format de fichier non supporté'}, status=400)
        if existing_variables:
            return JsonResponse({'status': 'exists', 'existing_variables': existing_variables})
        else:
            return JsonResponse({'status': 'no_duplicates'})

    return JsonResponse({'error': 'Requête invalide'}, status=400)


def get_surveys_by_collections(request):
    collections_ids = request.GET.get('collections_ids')
    if collections_ids:
        collections_ids = [int(id) for id in collections_ids.split(',')]
        surveys = Survey.objects.filter(subcollection__collection__id__in=collections_ids).order_by('name')
    else:
        surveys = Survey.objects.all().order_by('name')

    surveys_data = [{'id': survey.id, 'name': survey.name} for survey in surveys]
    return JsonResponse({'surveys': surveys_data})


def create_distributor(request):
    if request.method == "POST":
        name = request.POST.get('name')
        if name:
            Distributor.objects.get_or_create(name=name)
            return JsonResponse({"success": True, "message": "Diffuseur ajouté avec succès."})
        return JsonResponse({"success": False, "message": "Le nom du diffeuseur est requis."})
    return JsonResponse({"success": False, "message": "Requête invalide."})


def get_distributor(request):
    distributors = Distributor.objects.all().values("id", "name")
    return JsonResponse({"distributors": list(distributors)})




def get_subcollections_by_collections(request):
    collection_ids = request.GET.get('collections_ids', '').split(',')
    collection_ids = [id for id in collection_ids if id]

    if not collection_ids:
        subcollections = Subcollection.objects.all().order_by('name')
        surveys = Survey.objects.all().order_by('name')
    else:
        subcollections = Subcollection.objects.filter(collection_id__in=collection_ids).order_by('name')
        surveys = Survey.objects.filter(subcollection__collection_id__in=collection_ids).order_by('name')

    surveys = list(surveys)
    subcollections = list(subcollections)
    subcollections.sort(key=lambda sc: alphanum_key(sc.name))
    surveys.sort(key=lambda s: alphanum_key(s.name))

    data = {
        'subcollections': [{'id': sc.id, 'name': sc.name} for sc in subcollections],
        'surveys': [{'id': s.id, 'name': s.name} for s in surveys],
    }

    return JsonResponse(data)


def get_surveys_by_subcollections(request):
    subcollection_ids = request.GET.get('subcollections_ids', '').split(',')
    subcollection_ids = [id for id in subcollection_ids if id]

    if not subcollection_ids:
        collection_ids = request.GET.get('collections_ids', '').split(',')
        collection_ids = [id for id in collection_ids if id]

        if collection_ids:
            surveys = Survey.objects.filter(subcollection__collection_id__in=collection_ids).order_by('name')
        else:
            surveys = Survey.objects.all().order_by('name')
    else:
        surveys = Survey.objects.filter(subcollection_id__in=subcollection_ids).order_by('name')

    surveys = list(surveys)
    surveys.sort(key=lambda s: alphanum_key(s.name))

    data = {'surveys': [{'id': s.id, 'name': s.name} for s in surveys]}
    return JsonResponse(data)

def get_decades(request):
    # Récupérer les années uniques des enquêtes
    years = Survey.objects.values_list('start_date', flat=True).distinct()
    years = [year.year for year in years if year is not None]
    years = list(set(years))
    years.sort(reverse=True)

    # Regrouper les années par décennies
    decades = {}
    for year in years:
        decade = (year // 10) * 10
        if decade not in decades:
            decades[decade] = []
        decades[decade].append(year)
    # Préparer les données à renvoyer
    data = {'decades': decades}
    return JsonResponse(data)

def get_years_by_decade(request):
    try:
        decade = int(request.GET.get('decade', 0))
    except ValueError:
        return JsonResponse({'error': 'Invalid decade value'}, status=400)
    print("decade", decade)
    start_year = decade
    end_year = decade + 9

    years = Survey.objects.filter(start_date__year__range=(start_year, end_year)) \
                          .values_list('start_date__year', flat=True) \
                          .distinct()
    years = list(set(years))  # Éliminer les doublons
    years.sort()

    return JsonResponse({'years': years})