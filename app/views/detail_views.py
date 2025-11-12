# -- DJANGO
from django.shortcuts import get_object_or_404, render
from django.views import View

# -- LOCAL
from app.models import BindingSurveyRepresentedVariable


class QuestionDetailView(View):
    def get(self, request, id_quest, *args, **kwargs):
        search_params = request.GET.urlencode()
        question = get_object_or_404(BindingSurveyRepresentedVariable, id=id_quest)
        question_represented_var = question.variable
        question_conceptual_var = question_represented_var.conceptual_var
        question_survey = question.survey

        # Tri des catégories
        categories = sorted(
            question.variable.categories.all(),
            key=lambda x: (int(x.code) if x.code.isdigit() else float("inf"), x.code),
        )
        similar_representative_questions = (
            BindingSurveyRepresentedVariable.objects.filter(
                variable=question.variable, variable__is_unique=False
            ).exclude(id=question.id)
        )

        similar_conceptual_questions = (
            BindingSurveyRepresentedVariable.objects.filter(
                variable__conceptual_var=question.variable.conceptual_var,
                variable__conceptual_var__is_unique=False,
            )
            .exclude(id=question.id)
            .exclude(
                id__in=similar_representative_questions.values_list("id", flat=True)
            )
        )

        for q in similar_representative_questions:
            q.categories = sorted(
                q.variable.categories.all(),
                key=lambda x: (
                    int(x.code) if x.code.isdigit() else float("inf"),
                    x.code,
                ),
            )

        for q in similar_conceptual_questions:
            q.categories = sorted(
                q.variable.categories.all(),
                key=lambda x: (
                    int(x.code) if x.code.isdigit() else float("inf"),
                    x.code,
                ),
            )

        context = locals()
        return render(request, "question_detail.html", context)
