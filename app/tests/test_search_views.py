# -- STDLIB
from unittest.mock import MagicMock, patch

# -- DJANGO
from django.test import Client, TestCase
from django.urls import reverse

from app.models import Collection, ConceptualVariable, RepresentedVariable, Subcollection, Survey

# -- LOCAL
from app.views.search_views import SearchResultsDataView


class BaseSearchViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client = Client()

        cls.conceptual_var = ConceptualVariable.objects.create(
            internal_label="AGE_CONCEPT",
            is_unique=False,
        )
        cls.collection = Collection.objects.create(name="Collection Test")
        cls.subcollection = Subcollection.objects.create(
            name="Subcollection Test", collection=cls.collection
        )
        cls.survey = Survey.objects.create(
            name="Survey Test",
            subcollection=cls.subcollection,
            external_ref="doi:1234/test",
            start_date="2020-01-01",
        )
        cls.variable = RepresentedVariable.objects.create(
            conceptual_var=cls.conceptual_var,
            type="question",
            question_text="Quel âge avez-vous ?",
            internal_label="AGE",
            type_categories="text",
        )

        cls.binding_doc = {
            "variable_name": "Q1",
            "notes": "Notes test",
            "variable": {
                "internal_label": cls.variable.internal_label,
                "question_text": cls.variable.question_text,
            },
            "survey": {
                "name": cls.survey.name,
                "external_ref": cls.survey.external_ref,
            },
            "meta": {
                "id": "1",
                "highlight": {"variable.question_text": ["Quel <mark>âge</mark> avez-vous ?"]},
            },
        }


class RepresentedVariableSearchViewTest(BaseSearchViewTest):
    def test_get_context_data(self):
        response = self.client.get(reverse("app:representedvariable_search"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("collections", response.context)
        self.assertIn("variables", response.context)
        collections = list(response.context["collections"])
        self.assertEqual(len(collections), 1)
        self.assertEqual(str(collections[0]), "Collection Test")


class SearchResultsDataViewTest(BaseSearchViewTest):
    def setUp(self):
        self.url = reverse("api:search_results_data")

    @patch.object(SearchResultsDataView, "get_queryset")
    @patch.object(SearchResultsDataView, "build_filtered_search")
    @patch.object(SearchResultsDataView, "format_search_results")
    def test_post_with_valid_data(self, mock_format, mock_build, mock_queryset):
        mock_response = MagicMock()
        mock_response.hits.total.value = 1
        mock_queryset.return_value = mock_response

        mock_build.return_value.count.return_value = 1

        mock_format.return_value = [
            {
                "id": "1",
                "variable_name": "Q1",
                "question_text": "Quel âge avez-vous ?",
                "survey_name": "Survey Test",
                "notes": "Notes test",
                "categories": "<table class='styled-table'><tr><td>1</td><td>Catégorie test</td></tr></table>",
                "internal_label": "AGE",
                "is_category_search": False,
                "survey_doi": "doi:1234/test",
            }
        ]

        response = self.client.post(
            self.url,
            {
                "q": "âge",
                "search_location[]": ["questions"],
                "draw": "1"
            }
        )

        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertIn("data", json_data)
        self.assertEqual(len(json_data["data"]), 1)
        self.assertEqual(json_data["data"][0]["variable_name"], "Q1")

    @patch.object(SearchResultsDataView, "get_queryset")
    @patch.object(SearchResultsDataView, "build_filtered_search")
    @patch.object(SearchResultsDataView, "format_search_results")
    def test_post_with_no_results(self, mock_format, mock_build, mock_queryset):
        mock_response = MagicMock()
        mock_response.hits.total.value = 0
        mock_queryset.return_value = mock_response

        mock_build.return_value.count.return_value = 0
        mock_format.return_value = []

        response = self.client.post(
            self.url,
            {
                "q": "invalid_doi",
                "search_location[]": ["questions"],
                "draw": "1"
            }
        )

        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertIn("data", json_data)
        self.assertEqual(len(json_data["data"]), 0)

    @patch.object(SearchResultsDataView, "get_queryset", side_effect=Exception("Erreur"))
    def test_post_error_handling(self, mock_queryset):
        response = self.client.post(
            self.url,
            {"q": "âge", "search_location[]": ["questions"]}
        )

        self.assertEqual(response.status_code, 500)
        json_data = response.json()
        self.assertIn("error", json_data)
        self.assertEqual(json_data["error"], "Erreur")


class SearchResultsViewTest(BaseSearchViewTest):
    def test_search_results_view(self):
        response = self.client.get(
            reverse("app:search_results"),
            {"q": "âge", "search_location": ["questions"], "survey": ["1"]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("collections", response.context)
        self.assertIn("subcollections", response.context)
        self.assertIn("surveys", response.context)
        self.assertIn("search_location", response.context)
        self.assertEqual(response.context["search_query"], "âge")
        self.assertEqual(response.context["search_location"], ["questions"])
        self.assertEqual(response.context["selected_surveys"], ["1"])

    def test_search_results_view_session(self):
        self.client.get(
            reverse("app:search_results"),
            {"q": "âge", "search_location": ["questions"], "survey": ["1"]},
        )
        self.assertEqual(self.client.session["search_location"], ["questions"])
        self.assertEqual(self.client.session["selected_surveys"], ["1"])
