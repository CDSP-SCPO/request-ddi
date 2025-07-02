# -- STDLIB
import csv
from datetime import datetime
from html import unescape

# -- DJANGO
from django import forms
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
# views.py
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView
from django.views.generic.edit import FormView

# -- THIRDPARTY
from elasticsearch_dsl import Q

# -- BASEDEQUESTIONS (LOCAL)
from .dataImporter import DataImporter
from .documents import BindingSurveyDocument
from .forms import (
    CSVUploadFormCollection, CustomAuthenticationForm, XMLUploadForm,
)
from .models import (
    BindingSurveyRepresentedVariable, Collection, Distributor,
    RepresentedVariable, Subcollection, Survey,
)
from .parser import XMLParser
from .utils.timing import timed
from .views_utils import remove_html_tags


class XMLUploadView(FormView):
    template_name = 'upload_xml.html'
    form_class = XMLUploadForm
    success_url = reverse_lazy('app:representedvariable_search')

    def handle_error(self, message, form=None):
        self.errors = getattr(self, 'errors', [])
        self.errors.append(message)
        messages.error(self.request, message, extra_tags="safe")
        if form:
            return self.form_invalid(form)
        return None

    @timed
    @transaction.atomic
    def form_valid(self, form):
        self.errors = []  # Initialiser la liste des erreurs
        data = self.get_data(form)
        question_datas = list(self.convert_data(data))

        if self.errors:
            return self.form_invalid(form)

        importer = DataImporter()

        try:
            num_records, num_new_variables, num_new_bindings = importer.import_data(question_datas)

            # Récupérer les erreurs éventuelles après l'import
            if importer.errors:
                self.errors.extend(importer.errors)
                return self.form_invalid(form)

            messages.success(
                self.request,
                "Le fichier a été traité avec succès :<br/>"
                "<ul>"
                f"<li>{num_records} lignes ont été analysées.</li>"
                f"<li>{num_new_variables} nouvelles variables représentées créées.</li>"
                f"<li>{num_new_bindings} nouveaux bindings créés.</li>"
                "</ul>",
                extra_tags='safe'
            )
            return super().form_valid(form)

        except ValueError as ve:
            return self.handle_error(f"{ve}", form)

        except Exception as e:
            return self.handle_error(f"Erreur inattendue : {str(e)}", form)

    def form_invalid(self, form):
        error_messages = []

        # 1. Erreurs Django du formulaire
        for field, field_errors in form.errors.items():
            for error in field_errors:
                cleaned_error = str(error)
                error_messages.append(cleaned_error)

        # 2. Erreurs collectées par self.errors (parser, import, etc.)
        error_messages.extend(getattr(self, 'errors', []))

        if error_messages:
            messages.error(
                self.request,
                "<br/>".join(error_messages),
                extra_tags="safe"
            )

        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.add_form_to_context(context)
        return context

    def add_form_to_context(self, context):
        context['xml_form'] = XMLUploadForm()

    def get_data(self, form):
        files = self.request.FILES.getlist('xml_file')
        self.errors = []
        return files

    def convert_data(self, files):
        results = []
        seen_invalid_dois = set()
        for file in files:
            print(f"\n📂 Début du traitement du fichier : {file.name}")
            try:
                parser = XMLParser()
                result = parser.parse_file(file, seen_invalid_dois)
                self.errors.extend(parser.errors)
                if result:
                    print(f"✅ {len(result)} variables extraites du fichier {file.name}")
                    results.extend(result)
            except Exception as e:
                self.errors.append(f"Erreur lors de la lecture du fichier {file.name}: {str(e)}")
                print(f"❌ Erreur lors de la lecture du fichier {file.name}: {str(e)}")
        return results



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

        search = search.highlight_options(pre_tags=['<mark style="background-color: rgba(255, 70, 78, 0.15);">'],
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
            try:
                variable = getattr(result, 'variable', None)
                survey = getattr(result, 'survey', None)

                if not variable:
                    print(f"⚠️ Variable manquante pour le résultat ID {result.meta.id}")
                if not survey:
                    print(f"⚠️ Survey manquant pour le résultat ID {result.meta.id}")

                original_question = getattr(variable, 'question_text', "N/A")
                highlighted_question = (
                    result.meta.highlight['variable.question_text'][0]
                    if hasattr(result.meta, 'highlight') and 'variable.question_text' in result.meta.highlight
                    else original_question
                )

                categories = getattr(variable, 'categories', []) or []
                all_clean_categories = []
                category_matched = None

                if 'categories' in search_locations and hasattr(result.meta, 'highlight'):
                    if 'variable.categories.category_label' in result.meta.highlight:
                        category_highlight = result.meta.highlight['variable.categories.category_label']
                        category_matched = category_highlight[0] if category_highlight else None

                try:
                    sorted_categories = sorted(categories, key=lambda cat: (
                        int(cat.code) if cat.code.isdigit() else float('inf'), cat.code))
                except Exception as e:
                    print(f"❌ Erreur lors du tri des catégories pour ID {result.meta.id} : {e}")
                    sorted_categories = categories

                for cat in sorted_categories:
                    code = getattr(cat, 'code', 'N/A')
                    label = getattr(cat, 'category_label', 'N/A')
                    if category_matched and label == remove_html_tags(category_matched):
                        all_clean_categories.append(
                            f"<tr><td class='code-cell'><mark style='background-color: rgba(255, 70, 78, 0.15);'>{code}</mark></td><td class='text-cell'><mark style='background-color: rgba(255, 70, 78, 0.15);'>{label}</mark></td></tr>"
                        )
                    else:
                        all_clean_categories.append(
                            f"<tr><td class='code-cell'>{code}</td><td class='text-cell'>{label}</td></tr>"
                        )

                variable_name = getattr(result, 'variable_name', 'N/A')
                if 'variable_name' in search_locations and hasattr(result.meta,
                                                                   'highlight') and 'variable_name' in result.meta.highlight:
                    variable_name = result.meta.highlight['variable_name'][0]

                internal_label = getattr(variable, 'internal_label', 'N/A')
                if 'internal_label' in search_locations and hasattr(result.meta,
                                                                    'highlight') and 'variable.internal_label' in result.meta.highlight:
                    internal_label = result.meta.highlight['variable.internal_label'][0]

                survey_doi = getattr(survey, 'external_ref', "N/A")
                survey_name = getattr(survey, 'name', "N/A")

                data.append({
                    "id": result.meta.id,
                    "variable_name": variable_name,
                    "question_text": highlighted_question,
                    "survey_name": survey_name,
                    "notes": getattr(result, 'notes', "N/A"),
                    "categories": "<table class='styled-table'>" + "".join(all_clean_categories) + "</table>",
                    "internal_label": internal_label,
                    "is_category_search": is_category_search,
                    "survey_doi": survey_doi
                })

            except Exception as e:
                print(
                    f"❌ Erreur inattendue lors du traitement du résultat ID {getattr(result.meta, 'id', 'inconnu')} : {e}")

        return data

    def post(self, request, *args, **kwargs):

        try:
            response = self.get_queryset()
            total_records = self.build_filtered_search().count()
            filtered_records = response.hits.total.value
            search_locations = request.POST.getlist(
                'search_location[]',
                ['questions', 'categories', 'variable_name', 'internal_label']
            )
            data = self.format_search_results(response, search_locations)
            return JsonResponse({
                "recordsTotal": total_records,
                "recordsFiltered": filtered_records,
                "draw": int(request.POST.get('draw', 1)),
                "data": data
            })

        except Exception as e:
            print(f"❌ Erreur dans post(): {e}")
            # -- STDLIB
            import traceback
            traceback.print_exc()
            return JsonResponse({"error": str(e)}, status=500)


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
        survey_ids = request.GET.getlist('survey')
        collection_ids = request.GET.getlist('collections')
        sub_collection_ids = request.GET.getlist('sub_collections')
        years = request.GET.getlist('years')
        search_locations = request.GET.getlist('search_location')

        # Créer la réponse CSV
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="questions_export.csv"'

        # Définir les colonnes du CSV
        writer = csv.writer(response)
        writer.writerow(['doi', 'title', 'variable_name', 'variable_label', 'question_text', 'category_label', 'univers', 'notes'])

        # Récupérer toutes les questions et appliquer les filtres
        questions = BindingSurveyRepresentedVariable.objects.all()

        if selected_ids and any(selected_ids):
            questions = questions.filter(id__in=selected_ids)
        if survey_ids and any(survey_ids):
            questions = questions.filter(survey__id__in=survey_ids)
        if collection_ids and any(collection_ids):
            questions = questions.filter(survey__subcollection__collection__id__in=collection_ids)
        if sub_collection_ids and any(sub_collection_ids):
            questions = questions.filter(survey__subcollection__id__in=sub_collection_ids)
        if years and any(years):
            questions = questions.filter(survey__start_date__year__in=years)

        for question in questions.distinct():
            represented_var = question.variable
            if question:
                survey = question.survey
                variable_name = question.variable_name
                universe = question.universe
                notes = question.notes
            else:
                survey = None
                variable_name = ''
                universe = ''
                notes = ''

            categories = " | ".join([f"{cat.code},{cat.category_label}" for cat in represented_var.categories.all()])

            writer.writerow([
                survey.external_ref if survey else '',
                survey.name if survey else '',
                variable_name,
                represented_var.internal_label or '',
                represented_var.question_text or '',
                categories,
                universe,
                notes
            ])

        return response


class QuestionDetailView(View):
    def get(self, request, id, *args, **kwargs):
        search_params = request.GET.urlencode()
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

        for q in similar_representative_questions:
            q.categories = sorted(
                q.variable.categories.all(),
                key=lambda x: (int(x.code) if x.code.isdigit() else float('inf'), x.code)
            )

        for q in similar_conceptual_questions:
            q.categories = sorted(
                q.variable.categories.all(),
                key=lambda x: (int(x.code) if x.code.isdigit() else float('inf'), x.code)
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



def export_page(request):
    collections = Collection.objects.all()
    surveys = Survey.objects.all()
    context = locals()
    return render(request, 'export_csv.html', context)



