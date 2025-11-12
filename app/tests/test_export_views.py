import csv
from io import StringIO

from django.test import Client, TestCase
from django.urls import reverse

from app.models import (
    BindingSurveyRepresentedVariable,
    Category,
    ConceptualVariable,
    RepresentedVariable,
    Survey,
)


class ExportQuestionsCSVViewTest(TestCase):
    """Tests de la vue d'export CSV des questions."""

    @classmethod
    def setUpTestData(cls):
        cls.client = Client()

        cls.conceptual_var = ConceptualVariable.objects.create(
            internal_label="AGE_CONCEPT",
            is_unique=False,
        )
        cls.survey = Survey.objects.create(
            name="Survey Test",
            external_ref="doi:1234/test"
        )
        cls.variable = RepresentedVariable.objects.create(
            conceptual_var=cls.conceptual_var,
            question_text="Quel âge avez-vous ?",
            internal_label="AGE",
        )
        cls.question = BindingSurveyRepresentedVariable.objects.create(
            variable=cls.variable,
            survey=cls.survey,
            variable_name="Q1"
        )
        cls.category = Category.objects.create(code="1", category_label="Moins de 25 ans")
        cls.variable.categories.add(cls.category)

    def test_export_all_questions(self):
        """Teste l'export CSV sans filtre."""
        response = self.client.get(reverse("export_questions_csv"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="questions_export.csv"')

        content = response.content.decode("utf-8")
        reader = csv.reader(StringIO(content))
        rows = list(reader)
        self.assertEqual(len(rows), 2)  # En-tête + 1 question
        self.assertIn("Quel âge avez-vous ?", rows[1][0])

    def test_export_filtered_questions(self):
        """Teste l'export CSV avec filtres."""
        response = self.client.get(reverse("export_questions_csv"), {"ids": [self.question.id]})
        content = response.content.decode("utf-8")
        reader = csv.reader(StringIO(content))
        rows = list(reader)
        self.assertEqual(len(rows), 2)
        self.assertIn(str(self.question.id), content)
