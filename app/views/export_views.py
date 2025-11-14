# -- DJANGO
import csv

from django.http import HttpResponse
from django.shortcuts import render
from django.views import View

# -- LOCAL
from app.models import BindingSurveyRepresentedVariable, Collection, Survey
from app.views.mixins import staff_required_html


class ExportQuestionsCSVView(View):
    def get(self, request, *args, **kwargs):
        selected_ids = request.GET.getlist("ids")
        survey_ids = request.GET.getlist("survey")
        collection_ids = request.GET.getlist("collections")
        sub_collection_ids = request.GET.getlist("sub_collections")
        years = request.GET.getlist("years")

        # Créer la réponse CSV
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="questions_export.csv"'

        # Définir les colonnes du CSV
        writer = csv.writer(response)

        # Récupérer toutes les questions et appliquer les filtres
        questions = BindingSurveyRepresentedVariable.objects.all()

        if selected_ids and any(selected_ids):
            questions = questions.filter(id__in=selected_ids)
        if survey_ids and any(survey_ids):
            questions = questions.filter(survey__id__in=survey_ids)
        if collection_ids and any(collection_ids):
            questions = questions.filter(
                survey__subcollection__collection__id__in=collection_ids
            )
        if sub_collection_ids and any(sub_collection_ids):
            questions = questions.filter(
                survey__subcollection__id__in=sub_collection_ids
            )
        if years and any(years):
            questions = questions.filter(survey__start_date__year__in=years)

        questions = questions.distinct()
        max_vars = 0
        questions_data = []

        for question in questions:
            represented_var = question.variable
            categories = " | ".join(
                [
                    f"{cat.code},{cat.category_label}"
                    for cat in represented_var.categories.all()
                ]
            )
            associated_bindings = (
                represented_var.bindingsurveyrepresentedvariable_set.all()
            )
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

        dataset_var_headers = [f"dataset_var{i + 1}" for i in range(max_vars)]

        writer.writerow(
            ["question_text", "categories", "variable_label", *dataset_var_headers]
        )

        # Écrire les lignes
        for data in questions_data:
            row = [data["question_text"], data["categories"], data["variable_label"]]
            # Compléter avec des colonnes vides si nécessaire
            row += data["dataset_vars"] + [""] * (max_vars - len(data["dataset_vars"]))
            writer.writerow(row)

        return response

@staff_required_html
def export_page(request):
    collections = Collection.objects.all()
    surveys = Survey.objects.all()
    context = locals()
    return render(request, "export_csv.html", context)
