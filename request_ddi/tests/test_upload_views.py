import unittest
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from request_ddi.core.models import (
    BindingSurveyRepresentedVariable,
    Collection,
    ConceptualVariable,
    Distributor,
    RepresentedVariable,
    Subcollection,
    Survey,
)

from . import is_elasticsearch_available
from .mixins import MockElasticsearchMixin


class BaseUploadTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Création du client test
        cls.client = Client()
        cls.user = User.objects.create_user(
            username="admin",
            password="pwd",  # noqa: S106
            is_staff=True,
        )

    def setUp(self):
        self.client.login(username="admin", password="pwd")  # noqa: S106

    def login(self):
        self.client.force_login(self.user)


@unittest.skipIf(not is_elasticsearch_available(), "elastic search is required for this test")
class CSVUploadViewCollectionTest(MockElasticsearchMixin, BaseUploadTest):
    def test_form_valid_with_valid_csv_and_xml(self):
        self.login()
        csv_content = (
            "distributor,collection,sous-collection,doi,title,xml_lang,author,producer,start_date,"
            "geographic_coverage,geographic_unit,unit_of_analysis,contact,date_last_version\n"
            "Distrib,Collection,Subcollection,doi:1234/test,Survey Test,fr,Author,Producer,2020,France,,Individual,Contact,2020-01-01\n"
        )
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode(), content_type="text/csv")
        xml_content = """
        <root>
            <IDNo agency="DataCite">doi:1234/test</IDNo>
            <var name="Q1">
                <labl>Âge</labl>
                <qstn>
                    <qstnLit>Quel est votre âge ?</qstnLit>
                </qstn>
                <catgry>
                    <catValu>1</catValu>
                    <labl>18-25 ans</labl>
                    <catStat type="freq">26</catStat>
                </catgry>
            </var>
        </root>
        """
        response = self.client.post(
            reverse("request_ddi:upload_csv_collection"),
            {
                "csv_file": csv_file,
                "delimiter": ",",
                "xml_for_1234/test": xml_content,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertTrue(Survey.objects.filter(external_ref="doi:1234/test").exists())

    def test_form_valid_csv_without_xml(self):
        self.login()

        csv_content = (
            "distributor,collection,sous-collection,doi,title,xml_lang,author,producer,start_date,"
            "geographic_coverage,geographic_unit,unit_of_analysis,contact,date_last_version\n"
            "Distrib,Collection,Subcollection,doi:5678/test,Survey Test 2,fr,Author,Producer,2020,"
            "France,,Individual,Contact,2020-01-01\n"
        )
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode(), content_type="text/csv")

        response = self.client.post(
            reverse("request_ddi:upload_csv_collection"),
            {
                "csv_file": csv_file,
                "delimiter": ",",
            },
        )

        self.assertEqual(response.status_code, 400)
        json_response = response.json()
        self.assertEqual(json_response["status"], "error")
        self.assertIn("Aucun XML fourni", json_response["message"])

    def test_form_invalid_with_duplicate_doi(self):
        """Teste l'import d'un fichier CSV avec un DOI en double."""
        self.login()
        Distributor.objects.create(name="Distrib")
        Collection.objects.create(name="Collection", distributor=Distributor.objects.first())
        Subcollection.objects.create(name="Subcollection", collection=Collection.objects.first())
        Survey.objects.create(
            external_ref="doi:1234/test",
            name="Survey Test",
            subcollection=Subcollection.objects.first(),
        )

        csv_content = (
            "distributor,collection,sous-collection,doi,title,xml_lang,author,producer,start_date,"
            "geographic_coverage,geographic_unit,unit_of_analysis,contact,date_last_version\n"
            "Distrib,Collection,Subcollection,doi:1234/test,Survey Test,fr,Author,Producer,2020,France,,Individual,Contact,2020-01-01\n"
        )
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode(), content_type="text/csv")

        xml_content = """
        <root>
            <IDNo agency="DataCite">doi:1234/test</IDNo>
            <var name="Q1">
                <labl>Test</labl>
                <qstn><qstnLit>Test question</qstnLit></qstn>
                <catgry>
                    <catValu>1</catValu>
                    <labl>Test</labl>
                    <catStat type="freq">1</catStat>
                </catgry>
            </var>
        </root>
        """

        response = self.client.post(
            reverse("request_ddi:upload_csv_collection"),
            {
                "csv_file": csv_file,
                "delimiter": ",",
                "xml_for_1234/test": xml_content,
            },
        )

        self.assertEqual(response.status_code, 200)
        json_response = response.json()
        self.assertEqual(json_response["status"], "success")
        self.assertEqual(Survey.objects.filter(external_ref="doi:1234/test").count(), 1)

    def test_form_invalid_with_invalid_doi_format(self):
        """Teste l'import avec un DOI au mauvais format"""
        self.login()

        csv_content = (
            "distributor,collection,sous-collection,doi,title,xml_lang,author,producer,start_date,"
            "geographic_coverage,geographic_unit,unit_of_analysis,contact,date_last_version\n"
            "Distrib,Collection,Subcollection,1234/test,Survey Test,fr,Author,Producer,2020,"
            "France,,Individual,Contact,2020-01-01\n"
        )
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode(), content_type="text/csv")

        response = self.client.post(
            reverse("request_ddi:upload_csv_collection"),
            {
                "csv_file": csv_file,
                "delimiter": ",",
            },
        )

        self.assertEqual(response.status_code, 400)
        json_response = response.json()
        self.assertEqual(json_response["status"], "error")
        self.assertIn("n'est pas dans le bon format", json_response["message"])

    def test_form_invalid_with_malformed_xml(self):
        """Teste l'import avec un XML mal formé"""
        self.login()

        csv_content = (
            "distributor,collection,sous-collection,doi,title,xml_lang,author,producer,start_date,"
            "geographic_coverage,geographic_unit,unit_of_analysis,contact,date_last_version\n"
            "Distrib,Collection,Subcollection,doi:9999/test,Survey Test,fr,Author,Producer,2020,"
            "France,,Individual,Contact,2020-01-01\n"
        )
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode(), content_type="text/csv")

        # XML invalide
        xml_content = "<root><unclosed>"

        response = self.client.post(
            reverse("request_ddi:upload_csv_collection"),
            {
                "csv_file": csv_file,
                "delimiter": ",",
                "xml_for_9999/test": xml_content,
            },
        )

        self.assertEqual(response.status_code, 400)
        json_response = response.json()
        self.assertEqual(json_response["status"], "error")

    def test_form_invalid_with_missing_columns(self):
        """Teste l'import avec des colonnes manquantes dans le CSV"""
        self.login()

        csv_content = "doi,title\ndoi:1234/test,Survey Test\n"
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode(), content_type="text/csv")

        response = self.client.post(
            reverse("request_ddi:upload_csv_collection"),
            {"csv_file": csv_file, "delimiter": ","},
        )

        self.assertEqual(response.status_code, 400)
        json_response = response.json()
        self.assertEqual(json_response["status"], "error")

    def test_csv_with_multiple_surveys_and_xmls(self):
        """Teste l'import de plusieurs surveys avec leurs XMLs respectifs"""
        self.login()

        csv_content = (
            "distributor,collection,sous-collection,doi,title,xml_lang,author,producer,start_date,"
            "geographic_coverage,geographic_unit,unit_of_analysis,contact,date_last_version\n"
            "Distrib,Collection,Subcollection,doi:1234/test,Survey 1,fr,Author,Producer,2020,"
            "France,,Individual,Contact,2020-01-01\n"
            "Distrib,Collection,Subcollection,doi:5678/test,Survey 2,fr,Author,Producer,2021,"
            "France,,Individual,Contact,2021-01-01\n"
        )
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode(), content_type="text/csv")

        xml_content_1 = """
        <root>
            <IDNo agency="DataCite">doi:1234/test</IDNo>
            <var name="Q1">
                <labl>Question 1</labl>
                <qstn><qstnLit>Text 1</qstnLit></qstn>
                <catgry>
                    <catValu>1</catValu>
                    <labl>Option 1</labl>
                    <catStat type="freq">10</catStat>
                </catgry>
            </var>
        </root>
        """

        xml_content_2 = """
        <root>
            <IDNo agency="DataCite">doi:5678/test</IDNo>
            <var name="Q2">
                <labl>Question 2</labl>
                <qstn><qstnLit>Text 2</qstnLit></qstn>
                <catgry>
                    <catValu>1</catValu>
                    <labl>Option 2</labl>
                    <catStat type="freq">20</catStat>
                </catgry>
            </var>
        </root>
        """

        response = self.client.post(
            reverse("request_ddi:upload_csv_collection"),
            {
                "csv_file": csv_file,
                "delimiter": ",",
                "xml_for_1234/test": xml_content_1,
                "xml_for_5678/test": xml_content_2,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

        # Vérifier que les deux surveys ont été créées
        self.assertTrue(Survey.objects.filter(external_ref="doi:1234/test").exists())
        self.assertTrue(Survey.objects.filter(external_ref="doi:5678/test").exists())


@unittest.skipIf(not is_elasticsearch_available(), "elastic search is required for this test")
class CheckDuplicatesTest(BaseUploadTest):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.survey = Survey.objects.create(name="Survey Test", external_ref="doi:1234/test")
        conceptual_var = ConceptualVariable.objects.create(internal_label="Demo Var")
        represented_var = RepresentedVariable.objects.create(
            conceptual_var=conceptual_var,
            type="question",
            question_text="Quel âge avez-vous ?",
            internal_label="Q1",
            type_categories="text",
        )
        cls.question = BindingSurveyRepresentedVariable.objects.create(
            variable_name="Q1", survey=cls.survey, variable=represented_var, notes="", universe=""
        )

    @patch("request_ddi.views.upload_views.find_xml_file_id")
    @patch("request_ddi.views.upload_views.download_xml_file")
    def test_check_duplicates_with_duplicate(self, mock_download, mock_find):
        self.login()

        mock_find.return_value = "mock_file_id"
        mock_download.return_value = """
        <root>
            <var name="Q1"/>
        </root>
        """

        csv_content = (
            "distributor;collection;sous-collection;doi;title;xml_lang;author;producer;start_date;"
            "geographic_coverage;geographic_unit;unit_of_analysis;contact;date_last_version\n"
            "Distrib;Collection;Subcollection;doi:1234/test;Survey Test;fr;Author;Producer;2020;"
            "France;;Individual;Contact;2020-01-01\n"
        )
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode(), content_type="text/csv")

        response = self.client.post(reverse("request_ddi:check_duplicates"), {"csv_file": csv_file})
        self.assertEqual(response.status_code, 200)
        json_response = response.json()
        self.assertEqual(json_response["status"], "duplicates")
        self.assertIn("doi:1234/test", json_response["duplicates"])
        self.assertIn("Q1", json_response["duplicates"]["doi:1234/test"])

    @patch("request_ddi.views.upload_views.find_xml_file_id")
    @patch("request_ddi.views.upload_views.download_xml_file")
    def test_check_duplicates_with_no_duplicate(self, mock_download, mock_find):
        self.login()

        mock_find.return_value = "mock_file_id"
        mock_download.return_value = """
        <root>
            <var name="Q2"/>
        </root>
        """

        csv_content = (
            "distributor;collection;sous-collection;doi;title;xml_lang;author;producer;start_date;"
            "geographic_coverage;geographic_unit;unit_of_analysis;contact;date_last_version\n"
            "Distrib;Collection;Subcollection;doi:1234/test;Survey Test;fr;Author;Producer;2020;"
            "France;;Individual;Contact;2020-01-01\n"
        )
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode(), content_type="text/csv")

        response = self.client.post(reverse("request_ddi:check_duplicates"), {"csv_file": csv_file})
        self.assertEqual(response.status_code, 200)
        json_response = response.json()
        self.assertEqual(json_response["status"], "ok")
        self.assertIn("xml_contents", json_response)
