# -- STDLIB
import logging
from html import unescape

from django.http import JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

# -- DJANGO
from django.views.generic import ListView

# -- THIRDPARTY
# -- LOCAL
from request_ddi.core.documents import BindingSurveyDocument
from request_ddi.core.models import Collection, RepresentedVariable, Subcollection, Survey
from request_ddi.utils.timer import log_time
from request_ddi.views.utils_views import (
    ALL_SEARCH_LOCATIONS,
    validate_search_locations,
)

from .utils_views import remove_html_tags

logger = logging.getLogger(__name__)


@method_decorator(log_time, name="dispatch")
class RepresentedVariableSearchView(ListView):
    model = RepresentedVariable
    template_name = "homepage.html"  # Nom du template
    context_object_name = "variables"  # Nom du contexte utilisé dans le template

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["collections"] = Collection.objects.all()
        context["success_message"] = self.request.GET.get("success_message", None)
        context["upload_stats"] = self.request.GET.get("upload_stats", None)
        return context


@method_decorator(log_time, name="dispatch")
class SearchResultsDataView(ListView):
    model = BindingSurveyDocument
    context_object_name = "results"
    paginate_by = 10

    @csrf_exempt
    def dispatch(self, *args, **kwargs):
        if (
            "search_location" not in self.request.session
            or not self.request.session["search_location"]
        ):
            self.request.session["search_location"] = ALL_SEARCH_LOCATIONS
        return super().dispatch(*args, **kwargs)

    def build_filtered_search(self):
        search_value = unescape(self.request.POST.get("q", "").strip().lower())

        search_locations = validate_search_locations(self.request.POST.getlist("search_location"))
        survey_filter = [int(i) for i in self.request.POST.getlist("survey") if i.isdigit()]
        subcollection_filter = [
            int(i) for i in self.request.POST.getlist("sub_collection") if i.isdigit()
        ]
        collections_filter = [
            int(i) for i in self.request.POST.getlist("collection") if i.isdigit()
        ]
        years = [int(i) for i in self.request.POST.getlist("years") if i.isdigit()]

        search = BindingSurveyDocument.search_with_filters(
            query=search_value,
            search_locations=search_locations,
            survey_ids=survey_filter,
            collection_ids=collections_filter,
            sub_collection_ids=subcollection_filter,
            years=years,
            aggregations=True,
        )

        return (
            search.highlight_options(
                pre_tags=['<mark style="background-color: rgba(255, 70, 78, 0.15);">'],
                post_tags=["</mark>"],
                number_of_fragments=0,
                fragment_size=10000,
            )
            .highlight("variable.question_text", fragment_size=10000)
            .highlight("variable.categories.category_label", fragment_size=10000)
            .highlight("variable_name", fragment_size=10000)
            .highlight("variable.internal_label", fragment_size=10000)
        )

    def format_search_results(self, response, search_locations):  # noqa: C901
        data = []
        is_category_search = "categories" in search_locations

        for result in response.hits:
            try:
                variable = getattr(result, "variable", None)
                survey = getattr(result, "survey", None)

                if not variable:
                    logger.warning("⚠️ Variable manquante pour le résultat ID %s", result.meta.id)
                if not survey:
                    logger.warning("⚠️ Survey manquant pour le résultat ID %s", result.meta.id)

                original_question = getattr(variable, "question_text", "N/A")
                highlighted_question = (
                    result.meta.highlight["variable.question_text"][0]
                    if hasattr(result.meta, "highlight")
                    and "variable.question_text" in result.meta.highlight
                    else original_question
                )

                categories = getattr(variable, "categories", []) or []
                all_clean_categories = []
                category_matched = None

                if (
                    "categories" in search_locations
                    and hasattr(result.meta, "highlight")
                    and "variable.categories.category_label" in result.meta.highlight
                ):
                    category_highlight = result.meta.highlight["variable.categories.category_label"]
                    category_matched = category_highlight[0] if category_highlight else None

                try:
                    sorted_categories = sorted(
                        categories,
                        key=lambda cat: (
                            int(cat.code) if cat.code.isdigit() else float("inf"),
                            cat.code,
                        ),
                    )
                except Exception as e:
                    logger.error(
                        "❌ Erreur lors du tri des catégories pour ID %s : %s",
                        result.meta.id,
                        e,
                        exc_info=True,
                    )
                    sorted_categories = categories

                for cat in sorted_categories:
                    code = getattr(cat, "code", "N/A")
                    label = getattr(cat, "category_label", "N/A")
                    if category_matched and label == remove_html_tags(category_matched):
                        style = "style='background-color: rgba(255, 70, 78, 0.15);'"
                        all_clean_categories.append(
                            f"<tr><td class='code-cell'><mark {style}>{code}</mark></td><td class='text-cell'><mark {style}>{label}</mark></td></tr>"
                        )
                    else:
                        all_clean_categories.append(
                            f"<tr><td class='code-cell'>{code}</td><td class='text-cell'>{label}</td></tr>"
                        )

                variable_name = getattr(result, "variable_name", "N/A")
                if (
                    "variable_name" in search_locations
                    and hasattr(result.meta, "highlight")
                    and "variable_name" in result.meta.highlight
                ):
                    variable_name = result.meta.highlight["variable_name"][0]

                internal_label = getattr(variable, "internal_label", "N/A")
                if (
                    "internal_label" in search_locations
                    and hasattr(result.meta, "highlight")
                    and "variable.internal_label" in result.meta.highlight
                ):
                    internal_label = result.meta.highlight["variable.internal_label"][0]

                survey_doi = getattr(survey, "external_ref", "N/A")
                survey_name = getattr(survey, "name", "N/A")

                data.append(
                    {
                        "id": result.meta.id,
                        "variable_name": variable_name,
                        "question_text": highlighted_question,
                        "survey_name": survey_name,
                        "notes": getattr(result, "notes", "N/A"),
                        "categories": "<table class='styled-table'>"
                        + "".join(all_clean_categories)
                        + "</table>",
                        "internal_label": internal_label,
                        "is_category_search": is_category_search,
                        "survey_doi": survey_doi,
                    }
                )

            except Exception as e:
                logger.error(
                    "❌ Erreur inattendue lors du traitement du résultat ID %s : %s",
                    getattr(result.meta, "id", "inconnu"),
                    e,
                    exc_info=True,
                )

        return data

    def post(self, request, *args, **kwargs):
        try:
            search = self.build_filtered_search()
            start = int(self.request.POST.get("start", 0))
            limit = int(self.request.POST.get("limit", self.paginate_by))

            # Since we are sorting results on _score and survey.start_date, ES does not
            # track scores anymore (according to their docs). So, we need to explicitly
            # ask to track scores when sorting of results is required.
            # Ref: https://www.elastic.co/docs/reference/elasticsearch/rest-apis/sort-search-results#_track_scores
            search = search.extra(track_total_hits=True, track_scores=True)
            logger.debug("ES query: %s", search.to_dict())
            response = search[start : start + limit].execute()
            filtered_records = response.hits.total.value
            total_records = filtered_records
            search_locations = validate_search_locations(
                request.POST.getlist(
                    "search_location",
                )
            )
            data = self.format_search_results(response, search_locations)
            aggregations = format_aggregations(response)
            return JsonResponse(
                {
                    "recordsTotal": total_records,
                    "recordsFiltered": filtered_records,
                    "draw": int(request.POST.get("draw", 1)),
                    "data": data,
                    "aggregations": aggregations,
                }
            )

        except Exception as e:
            logger.exception("❌ Erreur dans post() : %s", e)
            return JsonResponse({"error": str(e)}, status=500)


@method_decorator(log_time, name="dispatch")
def search_results(request):
    collections = Collection.objects.all().order_by("name")
    subcollections = Subcollection.objects.all().order_by("name")
    surveys = Survey.objects.all().order_by("name")

    context = {
        "collections": collections,
        "subcollections": subcollections,
        "surveys": surveys,
        "show_search_bar": True,
    }
    return render(request, "search_results.html", context)


def format_aggregations(response):
    facets = response.aggregations.facets

    aggregations = {
        "surveys": [
            {"id": bucket.key, "count": bucket.doc_count}
            for bucket in facets.surveys_scope.surveys.buckets
        ],
        "subcollections": [
            {"id": bucket.key, "count": bucket.doc_count}
            for bucket in facets.subcollections_scope.subcollections.buckets
        ],
        "collections": [
            {"id": bucket.key, "count": bucket.doc_count}
            for bucket in facets.collections_scope.collections.buckets
        ],
        "years": [
            {
                "year": int(bucket.key_as_string),
                "count": bucket.doc_count,
            }
            for bucket in facets.years_scope.years.buckets
        ],
        "search_location": [],
    }

    for key in [
        "questions",
        "categories",
        "variable_name",
        "internal_label",
    ]:
        if hasattr(facets, key):
            aggregations["search_location"].append(
                {
                    "id": key,
                    "count": getattr(facets, key).doc_count,
                }
            )

    return aggregations
