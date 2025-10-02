# -- STDLIB
from html import unescape

# -- DJANGO
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.shortcuts import render
# -- THIRDPARTY
from elasticsearch_dsl import Q
# -- LOCAL
from app.documents import BindingSurveyDocument
from app.models import RepresentedVariable, Collection, Subcollection, Survey
from .utils_views import remove_html_tags


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