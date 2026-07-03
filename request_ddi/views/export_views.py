# -- DJANGO
import csv
import logging

from django.conf import settings
from django.http import StreamingHttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View

# -- THIRDPARTY
from elasticsearch import Elasticsearch

from request_ddi.core.documents import BindingSurveyDocument

# -- LOCAL
from request_ddi.core.models import (
    Collection,
    Subcollection,
    Survey,
)
from request_ddi.utils.timer import log_time
from request_ddi.views.mixins import staff_required_html

logger = logging.getLogger(__name__)

ES_EXPORT_BATCH_SIZE = 500


class Echo:
    """Adaptateur pseudo-fichier pour StreamingHttpResponse + csv.writer."""

    def write(self, value):
        return value


@method_decorator(log_time, name="dispatch")
class ExportQuestionsCSVView(View):
    def get(self, request, *args, **kwargs):
        selected_ids = request.GET.getlist("ids")
        query = request.GET.get("q", "").strip()
        survey_ids = request.GET.getlist("survey")
        collection_ids = request.GET.getlist("collections")
        sub_collection_ids = request.GET.getlist("sub_collections")
        search_locations = request.GET.getlist("search_location")
        raw_years = request.GET.getlist("years")

        years = self._parse_years(raw_years)

        # Using StreamingHttp allows to generate dynamically the csv lines, in order to have better efficiency

        response = StreamingHttpResponse(
            streaming_content=self._stream_csv(
                query=query,
                selected_ids=selected_ids,
                survey_ids=survey_ids,
                collection_ids=collection_ids,
                sub_collection_ids=sub_collection_ids,
                search_locations=search_locations,
                years=years,
            ),
            content_type="text/csv",
        )

        response["Content-Disposition"] = 'attachment; filename="questions_export.csv"'

        return response

    def _stream_csv(
        self,
        *,
        query,
        selected_ids,
        survey_ids,
        collection_ids,
        sub_collection_ids,
        search_locations,
        years,
    ):
        writer = csv.writer(Echo())

        es = Elasticsearch(**settings.ELASTICSEARCH_DSL["default"])
        es_query = (
            BindingSurveyDocument.search_with_filters(
                query=query,
                search_locations=search_locations,
                survey_ids=[int(i) for i in survey_ids if i.isdigit()],
                collection_ids=[int(i) for i in collection_ids if i.isdigit()],
                sub_collection_ids=[int(i) for i in sub_collection_ids if i.isdigit()],
                years=years,
                selected_ids=selected_ids,
            )
            .to_dict()
            .get("query", {"match_all": {}})
        )

        # We're keeping in memory all the variables seen, to be able to compare the new ones in order to determine whether they are identical variables or not
        pending = {}
        max_vars_seen = 0

        # We will use search_after (https://www.elastic.co/docs/reference/elasticsearch/rest-apis/paginate-search-results#search-after)
        # API to get paginated results.
        # The maximum number of results in a single search is 10000. We can increase
        # this limit by increasing index.max_result_window on index settings but that
        # would increase memory footprint.
        #
        # ES recommends to use search_after which is pagination of results.
        # Here we will sort the results based on variable.id and start the query from
        # id=0. This is what `search_after = [0]` signifies. We will update the
        # `search_after` for each page using the `sort` key from the last hit to get
        # next pages.
        total = 0
        search_after = [0]

        while True:
            result = es.search(
                index="binding_survey_variables",
                body={
                    "query": es_query,
                    "from": 0,
                    "size": ES_EXPORT_BATCH_SIZE,
                    "sort": [{"variable.id": "asc"}],
                    "search_after": search_after,
                    "_source": [
                        "variable.id",
                        "variable.question_text",
                        "variable.internal_label",
                        "variable.categories",
                        "survey.external_ref",
                        "variable_name",
                    ],
                },
            )

            hits = result["hits"]["hits"]

            for hit in hits:
                source = hit["_source"]
                variable = source.get("variable", {})
                survey = source.get("survey", {})

                question_text = variable.get("question_text", "")
                internal_label = variable.get("internal_label", "")
                categories_raw = variable.get("categories", [])
                categories_str = " | ".join(
                    f"{cat.get('code', '')},{cat.get('category_label', '')}"
                    for cat in categories_raw
                )
                external_ref = survey.get("external_ref", "")
                variable_name = source.get("variable_name", "")
                dataset_var = f"urn:ddi.cdsp:{external_ref}:{variable_name}" if external_ref else ""

                key = variable.get("id")

                if key not in pending:
                    pending[key] = {
                        "question_text": question_text,
                        "internal_label": internal_label,
                        "categories_str": categories_str,
                        "dataset_vars": [],
                    }
                pending[key]["dataset_vars"].append(dataset_var)
                max_vars_seen = max(max_vars_seen, len(pending[key]["dataset_vars"]))

            # sort key must exist in the hits but we are checking for it just in case.
            # In a strange situtation that we did not find `sort` key in the hits, bail!
            if not hits or "sort" not in hits[-1]:
                break

            # For the pagination
            search_after = hits[-1]["sort"]
            total += len(hits)

        logger.debug(
            "Nombre total de variables trouvées : %d et nombre total de variables uniques exportées : %d",
            total,
            len(pending),
        )
        dataset_var_headers = [f"dataset_var{i + 1}" for i in range(max_vars_seen)]
        yield writer.writerow(
            ["question_text", "categories", "variable_label", *dataset_var_headers]
        )

        for _key, data in pending.items():
            dvars = data["dataset_vars"]
            padding = [""] * (max_vars_seen - len(dvars))
            yield writer.writerow(
                [
                    data["question_text"],
                    data["categories_str"],
                    data["internal_label"],
                    *dvars,
                    *padding,
                ]
            )

    def _parse_years(self, raw_years):
        years = []
        for value in raw_years:
            if not value:
                continue
            for part in value.split(","):
                cleaned = part.strip()
                if cleaned.isdigit():
                    years.append(int(cleaned))
        return years


@log_time
@staff_required_html
def export_page(request):
    collections = Collection.objects.all()
    surveys = Survey.objects.all()
    subcollections = Subcollection.objects.all()
    context = locals()
    return render(request, "export_csv.html", context)
