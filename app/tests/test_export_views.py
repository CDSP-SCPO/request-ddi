import csv
from datetime import date
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
        cls.survey_2025 = Survey.objects.create(
            name="Survey 2025",
            external_ref="doi:2025",
            start_date=date(2025, 1, 1),
        )
        cls.variable_1 = RepresentedVariable.objects.create(
            conceptual_var=cls.conceptual_var,
            question_text="Quel âge avez-vous ?",
            internal_label="AGE",
        )
        cls.question_2025 = BindingSurveyRepresentedVariable.objects.create(
            variable=cls.variable_1,
            survey=cls.survey_2025,
            variable_name="Q1"
        )
        cls.category = Category.objects.create(code="1", category_label="Moins de 25 ans")
        cls.variable_1.categories.add(cls.category)

        # Surveys supplémentaires pour tests years
        cls.survey_2022 = Survey.objects.create(
            name="Survey 2022",
            external_ref="doi:2022",
            start_date=date(2022, 6, 1),
        )
        cls.survey_2024 = Survey.objects.create(
            name="Survey 2024",
            external_ref="doi:2024",
            start_date=date(2024, 5, 1),
        )

        cls.variable_2 = RepresentedVariable.objects.create(
            conceptual_var=cls.conceptual_var,
            question_text="Question année spécifique",
            internal_label="VAR2",
        )
        cls.question_2022 = BindingSurveyRepresentedVariable.objects.create(
            variable=cls.variable_2,
            survey=cls.survey_2022,
            variable_name="Q2"
        )
        cls.question_2024 = BindingSurveyRepresentedVariable.objects.create(
            variable=cls.variable_2,
            survey=cls.survey_2024,
            variable_name="Q3"
        )

    def test_export_all_questions(self):
        """Teste l'export CSV sans filtre."""
        response = self.client.get(reverse("export_questions_csv"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="questions_export.csv"')

        content = response.content.decode("utf-8")
        reader = csv.reader(StringIO(content))
        rows = list(reader)

        # Header + 3 questions
        self.assertEqual(len(rows), 4)
        row_texts = [row[0] for row in rows[1:]]
        self.assertIn("Quel âge avez-vous ?", row_texts)
        self.assertIn("Question année spécifique", row_texts)

    def test_export_single_year(self):
        """Teste l'export CSV avec une seule année (2022)."""
        response = self.client.get(
            reverse("export_questions_csv"),
            {"years": ["2022"]}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        reader = csv.reader(StringIO(content))
        rows = list(reader)

        # Header + 1 ligne (une variable)
        self.assertEqual(len(rows), 2)

        row_texts = [row[0] for row in rows[1:]]
        self.assertIn("Question année spécifique", row_texts)

        # dataset_vars = tous les bindings liés à la variable (Q2 et Q3)
        dataset_vars_str = rows[1][3]  # dataset_var1
        self.assertIn("Q2", dataset_vars_str)
        self.assertNotIn("Q3",
                         dataset_vars_str)  # Q3 est un binding sur 2024, mais il est un binding de la même variable

    def test_export_multiple_years(self):
        """Teste l'export CSV avec plusieurs années (2022 et 2024)."""
        response = self.client.get(
            reverse("export_questions_csv"),
            {"years": ["2022,2024"]}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        reader = csv.reader(StringIO(content))
        rows = list(reader)

        # Header + 2 lignes si variables distinctes, sinon 1 ligne par variable
        self.assertEqual(len(rows), 3)  # header + 2 variables

