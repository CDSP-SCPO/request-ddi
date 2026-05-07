import csv
from datetime import date
from io import StringIO
from unittest.mock import MagicMock, patch

from django.test import Client, TestCase
from django.urls import reverse

from request_ddi.core.models import (
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
            variable=cls.variable_1, survey=cls.survey_2025, variable_name="Q1"
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
            variable=cls.variable_2, survey=cls.survey_2022, variable_name="Q2"
        )
        cls.question_2024 = BindingSurveyRepresentedVariable.objects.create(
            variable=cls.variable_2, survey=cls.survey_2024, variable_name="Q3"
        )

    def _make_es_hit(self, variable, survey, variable_name):
        return {
            "_source": {
                "variable": {
                    "id": variable.id,
                    "question_text": variable.question_text,
                    "internal_label": variable.internal_label,
                    "categories": [
                        {"code": c.code, "category_label": c.category_label}
                        for c in variable.categories.all()
                    ],
                },
                "survey": {"external_ref": survey.external_ref},
                "variable_name": variable_name,
            }
        }

    def _mock_es_response(self, hits):
        mock_es_instance = MagicMock()
        mock_es_instance.search.return_value = {
            "hits": {
                "total": {"value": len(hits)},
                "hits": hits,
            }
        }
        mock_es_class = MagicMock(return_value=mock_es_instance)
        return mock_es_class

    def test_export_all_questions(self):
        """Teste l'export CSV sans filtre."""
        hits = [
            self._make_es_hit(self.variable_1, self.survey_2025, "Q1"),
            self._make_es_hit(self.variable_2, self.survey_2022, "Q2"),
        ]
        with patch(
            "request_ddi.views.export_views.Elasticsearch", new=self._mock_es_response(hits)
        ):
            response = self.client.get(
                reverse("export_questions_csv"),
                {"ids": [str(self.variable_1.id), str(self.variable_2.id)]},
            )
            content = b"".join(response.streaming_content).decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertEqual(
            response["Content-Disposition"], 'attachment; filename="questions_export.csv"'
        )
        reader = csv.reader(StringIO(content))
        rows = list(reader)

        # Header + 2 variables distinctes
        self.assertEqual(len(rows), 3)
        row_texts = [row[0] for row in rows[1:]]
        self.assertIn("Quel âge avez-vous ?", row_texts)
        self.assertIn("Question année spécifique", row_texts)

        # Vérifie que les dataset_vars sont bien présents
        for row in rows[1:]:
            self.assertTrue(any(row[3:]))  # Au moins un dataset_var

    def test_export_single_year(self):
        """Teste l'export CSV avec une seule année (2022)."""
        hits = [self._make_es_hit(self.variable_2, self.survey_2022, "Q2")]
        with patch(
            "request_ddi.views.export_views.Elasticsearch", new=self._mock_es_response(hits)
        ):
            response = self.client.get(
                reverse("export_questions_csv"),
                {"years": ["2022"], "ids": [str(self.variable_2.id)]},
            )
            content = b"".join(response.streaming_content).decode("utf-8")

        self.assertEqual(response.status_code, 200)
        reader = csv.reader(StringIO(content))
        rows = list(reader)

        # Header + 1 ligne (une variable)
        self.assertEqual(len(rows), 2)

        row_texts = [row[0] for row in rows[1:]]
        self.assertIn("Question année spécifique", row_texts)

        # Vérifie que seul le binding 2022 est présent
        dataset_vars = [cell for cell in rows[1][3:] if cell]
        self.assertEqual(len(dataset_vars), 1)
        self.assertIn("urn:ddi.cdsp:doi:2022:Q2", dataset_vars[0])

    def test_export_multiple_years(self):
        """Teste l'export CSV avec plusieurs années (2022 et 2024)."""
        hits = [
            self._make_es_hit(self.variable_2, self.survey_2022, "Q2"),
            self._make_es_hit(self.variable_2, self.survey_2024, "Q3"),
        ]
        with patch(
            "request_ddi.views.export_views.Elasticsearch", new=self._mock_es_response(hits)
        ):
            response = self.client.get(
                reverse("export_questions_csv"),
                {"years": ["2022,2024"], "ids": [str(self.variable_2.id)]},
            )
            content = b"".join(response.streaming_content).decode("utf-8")

        self.assertEqual(response.status_code, 200)
        reader = csv.reader(StringIO(content))
        rows = list(reader)

        # Header + 1 ligne (même variable, 2 bindings)
        self.assertEqual(len(rows), 2)

        # Vérifie que les 2 bindings sont présents
        dataset_vars = [cell for cell in rows[1][3:] if cell]
        self.assertEqual(len(dataset_vars), 2)
        self.assertIn("urn:ddi.cdsp:doi:2022:Q2", dataset_vars)
        self.assertIn("urn:ddi.cdsp:doi:2024:Q3", dataset_vars)

    def test_export_with_survey_filter(self):
        """Teste l'export CSV avec un filtre sur une survey spécifique."""
        hits = [self._make_es_hit(self.variable_2, self.survey_2022, "Q2")]
        with patch(
            "request_ddi.views.export_views.Elasticsearch", new=self._mock_es_response(hits)
        ):
            response = self.client.get(
                reverse("export_questions_csv"),
                {"survey": [str(self.survey_2022.id)], "ids": [str(self.variable_2.id)]},
            )
            content = b"".join(response.streaming_content).decode("utf-8")

        self.assertEqual(response.status_code, 200)
        reader = csv.reader(StringIO(content))
        rows = list(reader)

        # Header + 1 ligne (1 variable avec un binding sur la survey 2022)
        self.assertEqual(len(rows), 2)

        row_texts = [row[0] for row in rows[1:]]
        self.assertIn("Question année spécifique", row_texts)

        # Vérifie que seul le binding de la survey 2022 est présent
        dataset_vars = [cell for cell in rows[1][3:] if cell]
        self.assertEqual(len(dataset_vars), 1)
        self.assertIn("urn:ddi.cdsp:doi:2022:Q2", dataset_vars[0])
