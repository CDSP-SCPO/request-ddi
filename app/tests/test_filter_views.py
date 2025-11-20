from django.test import Client, TestCase
from django.urls import reverse

from app.models import Collection, Subcollection, Survey


class JSONViewsTest(TestCase):
    """Tests d’intégration des vues JSON pour collections, subcollections et surveys.""" # noqa: RUF002

    @classmethod
    def setUpTestData(cls):
        cls.client = Client()
        cls.collection = Collection.objects.create(name="Collection Test")
        cls.subcollection = Subcollection.objects.create(
            name="Subcollection Test",
            collection=cls.collection
        )
        cls.survey = Survey.objects.create(
            name="Survey Test",
            subcollection=cls.subcollection,
            start_date="2020-01-01"
        )

    # The test `test_get_surveys_by_collections` has been removed
    # because the `get_surveys_by_collections` endpoint no longer exists.


    def test_get_subcollections_by_collections(self):
        """Teste la récupération des subcollections et surveys par collections."""
        response = self.client.get(
            reverse("api:get_subcollections_by_collections"),
            {"collections_ids": str(self.collection.id)}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("subcollections", data)
        self.assertIn("surveys", data)
        self.assertEqual(len(data["subcollections"]), 1)
        self.assertEqual(len(data["surveys"]), 1)

    def test_get_decades(self):
        """Teste le groupement des années par décennies."""
        Survey.objects.create(
            name="Survey 2010",
            subcollection=self.subcollection,
            start_date="2010-01-01",
            external_ref="doi:1234/2010"
        )

        response = self.client.get(
            reverse("api:get_decades"),
            {"collections_ids": str(self.collection.id)}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("decades", data)
        self.assertIn("2010", data["decades"])

    def test_get_years_by_decade(self):
        """Teste la récupération des années par décennie."""
        response = self.client.get(
            reverse("api:get_years_by_decade"),
            {
                "decade": "2020",
                "collections_ids": str(self.collection.id),
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("years", data)
        self.assertEqual(data["years"], [2020])
