# -- DJANGO
import csv

from django.http import HttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View

# -- LOCAL
from app.models import BindingSurveyRepresentedVariable, Collection, Subcollection, Survey
from app.views.mixins import staff_required_html
from decorators.timer import log_time


@method_decorator(log_time, name="dispatch")
class ExportQuestionsCSVView(View):
    def get(self, request, *args, **kwargs):
        selected_ids = request.GET.getlist("ids")
        survey_ids = request.GET.getlist("survey")
        collection_ids = request.GET.getlist("collections")
        sub_collection_ids = request.GET.getlist("sub_collections")
        raw_years = request.GET.getlist("years")

        years = self._parse_years(raw_years)

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="questions_export.csv"'

        writer = csv.writer(response)

        questions = self._filter_questions(
            selected_ids=selected_ids,
            survey_ids=survey_ids,
            collection_ids=collection_ids,
            sub_collection_ids=sub_collection_ids,
            years=years,
        )

        questions_data, max_vars = self._collect_questions_data(questions)

        dataset_var_headers = [f"dataset_var{i + 1}" for i in range(max_vars)]
        writer.writerow(["question_text", "categories", "variable_label", *dataset_var_headers])

        for data in questions_data:
            row = [
                data["question_text"],
                data["categories"],
                data["variable_label"],
                *data["dataset_vars"],
                *[""] * (max_vars - len(data["dataset_vars"])),
            ]
            writer.writerow(row)

        return response

    # -------------------------
    # Helpers
    # -------------------------

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

    def _filter_questions(
        self,
        *,
        selected_ids,
        survey_ids,
        collection_ids,
        sub_collection_ids,
        years,
    ):
        qs = BindingSurveyRepresentedVariable.objects.all()

        if selected_ids and any(selected_ids):
            qs = qs.filter(id__in=selected_ids)

        if survey_ids and any(survey_ids):
            qs = qs.filter(survey__id__in=survey_ids)

        if collection_ids and any(collection_ids):
            qs = qs.filter(survey__subcollection__collection__id__in=collection_ids)

        if sub_collection_ids and any(sub_collection_ids):
            qs = qs.filter(survey__subcollection__id__in=sub_collection_ids)

        if years:
            qs = qs.filter(survey__start_date__year__in=years)

        return qs.distinct()

    def _collect_questions_data(self, questions):
        questions_data = []
        max_vars = 0

        for question in questions:
            represented_var = question.variable

            categories = " | ".join(
                f"{cat.code},{cat.category_label}"
                for cat in represented_var.categories.all()
            )

            associated_bindings = represented_var.bindingsurveyrepresentedvariable_set.all()

            dataset_vars = [
                f"urn:ddi.cdsp:{binding.survey.external_ref}:{binding.variable_name}"
                for binding in associated_bindings
            ]

            max_vars = max(max_vars, len(dataset_vars))

            questions_data.append(
                {
                    "question_text": represented_var.question_text,
                    "categories": categories,
                    "variable_label": represented_var.internal_label,
                    "dataset_vars": dataset_vars,
                }
            )

        return questions_data, max_vars

@log_time
@staff_required_html
def export_page(request):
    collections = Collection.objects.all()
    surveys = Survey.objects.all()
    subcollections = Subcollection.objects.all()
    context = locals()
    return render(request, "export_csv.html", context)
