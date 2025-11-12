from django.test import Client, TestCase
from django.urls import reverse

from app.models import (
    BindingSurveyRepresentedVariable,
    Category,
    ConceptualVariable,
    RepresentedVariable,
    Survey,
)


class QuestionDetailViewTest(TestCase):
    """Tests de la vue de détail des questions et de leurs catégories."""

    @classmethod
    def setUpTestData(cls):
        cls.client = Client()
        cls.conceptual_var = ConceptualVariable.objects.create(
            internal_label="AGE_CONCEPT",
            is_unique=False
        )

        cls.variable = RepresentedVariable.objects.create(
            conceptual_var=cls.conceptual_var,
            question_text="Quel âge avez-vous ?",
            internal_label="AGE",
            type_categories="text",
        )

        cls.survey = Survey.objects.create(
            name="Survey Test",
            external_ref="doi:1234/test"
        )

        cls.question = BindingSurveyRepresentedVariable.objects.create(
            variable=cls.variable,
            survey=cls.survey,
            variable_name="Q1"
        )

        cls.category1 = Category.objects.create(code="1", category_label="Moins de 25 ans")
        cls.category2 = Category.objects.create(code="2", category_label="25 ans ou plus")
        cls.category3 = Category.objects.create(code="10", category_label="Autre")
        cls.variable.categories.add(cls.category1, cls.category2, cls.category3)

    def test_get_existing_question(self):
        """Teste que la vue retourne bien la question et ses catégories triées."""
        response = self.client.get(reverse("app:question_detail", args=[self.question.id]))
        self.assertEqual(response.status_code, 200)

        context = response.context
        self.assertIn("question", context)
        self.assertIn("categories", context)
        self.assertEqual(len(context["categories"]), 3)

        codes = [cat.code for cat in context["categories"]]
        self.assertEqual(codes, ["1", "2", "10"])

    def test_get_nonexistent_question(self):
        """Teste qu'une 404 est levée si la question n'existe pas."""
        response = self.client.get(reverse("app:question_detail", args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_similar_questions(self):
        """Teste que les questions similaires sont bien filtrées et excluent la question courante."""
        similar_question = BindingSurveyRepresentedVariable.objects.create(
            variable=self.variable,
            survey=self.survey,
            variable_name="Q2"
        )

        response = self.client.get(reverse("app:question_detail", args=[self.question.id]))
        context = response.context

        self.assertIn("similar_representative_questions", context)
        similar_questions = context["similar_representative_questions"]
        self.assertEqual(len(similar_questions), 1)
        self.assertEqual(similar_questions[0].id, similar_question.id)
