from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.tasks.base import TaskResultStatus
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

from .mixins import MockElasticsearchMixin
from .utils import wait_task


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


class DDICImportViewCollectionTest(MockElasticsearchMixin, BaseUploadTest):
    """For the following unit tests if we need to debug the tests to understand
    which SQL statements are being executed, we can use the following snippet:

    # # Useful for debugging tests. This context manager prints all the SQL queries
    # # executed against the DB.
    # #
    # from django.db import connection
    # from django.test.utils import CaptureQueriesContext
    # with CaptureQueriesContext(connection) as ctx:
    #      commands to run...
    #      print(ctx.captured_queries)
    #
    """

    @patch("request_ddi.core.parser.download_xml_file")
    def test_form_valid_with_valid_csv_and_xml(self, mock_download):
        self.login()
        csv_content = (
            "distributor,collection,sub_collection,doi,title,xml_lang,author,producer,start_date,"
            "geographic_coverage,geographic_unit,unit_of_analysis,contact,date_last_version,url\n"
            "Distrib,Collection,Subcollection,doi:1234/test,Survey Test,fr,Author,Producer,2020,France,,Individual,Contact,2020-01-01,https://example.com/xml/\n"
        )
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode(), content_type="text/csv")
        xml_content = """
        <root>
            <IDNo agency="DataCite">doi:1234/test</IDNo>
            <titl>Test</titl>
            <timePrd date="1982" event="start"/>
            <verStmt>
                <version date="2018-01-26">Version 1</version>
            </verStmt>
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

        mock_download.return_value = xml_content
        response = self.client.post(
            reverse("request_ddi:import_ddic"),
            {"csv_file": csv_file, "delimiter": ","},
        )

        # Wait for task to finish
        task_status, _ = wait_task()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertEqual(task_status, TaskResultStatus.SUCCESSFUL)
        self.assertTrue(Survey.objects.filter(external_ref="doi:1234/test").exists())

    def test_form_valid_csv_without_xml(self):
        self.login()

        csv_content = (
            "distributor,collection,sub_collection,doi,title,xml_lang,author,producer,start_date,"
            "geographic_coverage,geographic_unit,unit_of_analysis,contact,date_last_version,url\n"
            "Distrib,Collection,Subcollection,doi:5678/test,Survey Test 2,fr,Author,Producer,2020,"
            "France,,Individual,Contact,2020-01-01,https://example.com/xml/\n"
        )
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode(), content_type="text/csv")

        response = self.client.post(
            reverse("request_ddi:import_ddic"),
            {
                "csv_file": csv_file,
                "delimiter": ",",
            },
        )

        # Wait for task to finish
        task_status, traceback = wait_task()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertEqual(task_status, TaskResultStatus.FAILED)
        self.assertIn("404 Client Error", traceback)

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
            "distributor,collection,sub_collection,doi,title,xml_lang,author,producer,start_date,"
            "geographic_coverage,geographic_unit,unit_of_analysis,contact,date_last_version,url\n"
            "Distrib,Collection,Subcollection,doi:1234/test,Survey Test,fr,Author,Producer,2020,France,,Individual,Contact,2020-01-01,https://example.com/xml/\n"
        )
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode(), content_type="text/csv")

        response = self.client.post(
            reverse("request_ddi:import_ddic"),
            {"csv_file": csv_file, "delimiter": ","},
        )
        self.assertEqual(response.status_code, 207)
        json_response = response.json()
        self.assertEqual(json_response["status"], "partial_success")
        self.assertEqual(Survey.objects.filter(external_ref="doi:1234/test").count(), 1)

    def test_form_invalid_with_invalid_doi_format(self):
        """Teste l'import avec un DOI au mauvais format"""
        self.login()

        csv_content = (
            "distributor,collection,sub_collection,doi,title,xml_lang,author,producer,start_date,"
            "geographic_coverage,geographic_unit,unit_of_analysis,contact,date_last_version,url\n"
            "Distrib,Collection,Subcollection,1234/test,Survey Test,fr,Author,Producer,2020,"
            "France,,Individual,Contact,2020-01-01,https://example.com/xml/\n"
        )
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode(), content_type="text/csv")

        response = self.client.post(
            reverse("request_ddi:import_ddic"),
            {
                "csv_file": csv_file,
                "delimiter": ",",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "error")
        self.assertTrue(any("n'est pas dans le bon format" in e for e in response.json()["errors"]))

    @patch("request_ddi.core.parser.download_xml_file")
    def test_form_invalid_with_malformed_xml(self, mock_download):
        """Teste l'import avec un XML mal formé"""
        self.login()

        csv_content = (
            "distributor,collection,sub_collection,doi,title,xml_lang,author,producer,start_date,"
            "geographic_coverage,geographic_unit,unit_of_analysis,contact,date_last_version,url\n"
            "Distrib,Collection,Subcollection,doi:9999/test,Survey Test,fr,Author,Producer,2020,"
            "France,,Individual,Contact,2020-01-01,https://example.com/xml/\n"
        )
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode(), content_type="text/csv")

        # XML invalide
        mock_download.return_value = "<root><unclosed>"

        response = self.client.post(
            reverse("request_ddi:import_ddic"),
            {
                "csv_file": csv_file,
                "delimiter": ",",
            },
        )

        # Wait for task to finish
        task_status, traceback = wait_task()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(task_status, TaskResultStatus.FAILED)
        self.assertIn("InvalidDOIError", traceback)

    def test_form_invalid_with_missing_columns(self):
        """Teste l'import avec des colonnes manquantes dans le CSV"""
        self.login()

        csv_content = "doi,title\ndoi:1234/test,Survey Test\n"
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode(), content_type="text/csv")

        response = self.client.post(
            reverse("request_ddi:import_ddic"),
            {"csv_file": csv_file, "delimiter": ","},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "error")
        self.assertIn("Les colonnes suivantes sont manquantes", response.json()["message"])

    @patch("request_ddi.core.parser.download_xml_file")
    def test_csv_with_multiple_surveys_and_xmls(self, mock_download):
        """Teste l'import de plusieurs surveys avec leurs XMLs respectifs"""
        self.login()

        csv_content = (
            "distributor,collection,sub_collection,doi,title,xml_lang,author,producer,start_date,"
            "geographic_coverage,geographic_unit,unit_of_analysis,contact,date_last_version,url\n"
            "Distrib,Collection,Subcollection,doi:1234/test,Survey 1,fr,Author,Producer,2020,"
            "France,,Individual,Contact,2020-01-01,https://example.com/xml/1234\n"
            "Distrib,Collection,Subcollection,doi:5678/test,Survey 2,fr,Author,Producer,2021,"
            "France,,Individual,Contact,2021-01-01,https://example.com/xml/5678\n"
        )
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode(), content_type="text/csv")

        xml_content_1 = """
        <root>
            <IDNo agency="DataCite">doi:1234/test</IDNo>
            <titl>Test</titl>
            <timePrd date="1982" event="start"/>
            <verStmt>
                <version date="2018-01-26">Version 1</version>
            </verStmt>
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
            <titl>Test</titl>
            <timePrd date="1982" event="start"/>
            <verStmt>
                <version date="2018-01-26">Version 1</version>
            </verStmt>
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

        mock_download.side_effect = lambda url: xml_content_1 if "1234" in url else xml_content_2

        response = self.client.post(
            reverse("request_ddi:import_ddic"),
            {"csv_file": csv_file, "delimiter": ","},
        )

        # Wait for task to finish
        task_status, _ = wait_task()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertEqual(task_status, TaskResultStatus.SUCCESSFUL)
        self.assertTrue(Survey.objects.filter(external_ref="doi:1234/test").exists())
        self.assertTrue(Survey.objects.filter(external_ref="doi:5678/test").exists())

    @patch("request_ddi.core.parser.download_xml_file")
    def test_csv_with_multiple_surveys_and_xmls_with_multiple_csv_files(self, mock_download):
        """Teste l'import de plusieurs surveys avec leurs XMLs respectifs dans plusieurs fichiers CSV"""
        self.login()

        csv_content_1 = (
            "distributor,collection,sub_collection,doi,title,xml_lang,author,producer,start_date,"
            "geographic_coverage,geographic_unit,unit_of_analysis,contact,date_last_version,url\n"
            "Distrib,Collection,Subcollection,doi:1234/test,Survey 1,fr,Author,Producer,2020,"
            "France,,Individual,Contact,2020-01-01,https://example.com/xml/1234\n"
        )
        csv_content_2 = (
            "distributor,collection,sub_collection,doi,title,xml_lang,author,producer,start_date,"
            "geographic_coverage,geographic_unit,unit_of_analysis,contact,date_last_version,url\n"
            "Distrib,Collection,Subcollection,doi:5678/test,Survey 2,fr,Author,Producer,2021,"
            "France,,Individual,Contact,2021-01-01,https://example.com/xml/5678\n"
        )
        csv_file_1 = SimpleUploadedFile(
            "test1.csv", csv_content_1.encode(), content_type="text/csv"
        )
        csv_file_2 = SimpleUploadedFile(
            "test2.csv", csv_content_2.encode(), content_type="text/csv"
        )

        xml_content_1 = """
        <root>
            <IDNo agency="DataCite">doi:1234/test</IDNo>
            <titl>Test</titl>
            <timePrd date="1982" event="start"/>
            <verStmt>
                <version date="2018-01-26">Version 1</version>
            </verStmt>
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
            <titl>Test</titl>
            <timePrd date="1982" event="start"/>
            <verStmt>
                <version date="2018-01-26">Version 1</version>
            </verStmt>
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

        mock_download.side_effect = lambda url: xml_content_1 if "1234" in url else xml_content_2

        response = self.client.post(
            reverse("request_ddi:import_ddic"),
            {"csv_file": [csv_file_1, csv_file_2], "delimiter": ","},
        )

        # Wait for task to finish
        task_status, _ = wait_task()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertEqual(task_status, TaskResultStatus.SUCCESSFUL)
        self.assertTrue(Survey.objects.filter(external_ref="doi:1234/test").exists())
        self.assertTrue(Survey.objects.filter(external_ref="doi:5678/test").exists())

    @patch("request_ddi.core.parser.download_xml_file")
    def test_csv_with_same_question_text_in_same_xml(self, mock_download):
        """Test when multiple variables in same survey have same question text but different labels"""
        self.login()

        csv_content = (
            "distributor,collection,sub_collection,doi,title,xml_lang,author,producer,start_date,"
            "geographic_coverage,geographic_unit,unit_of_analysis,contact,date_last_version,url\n"
            "Distrib,Collection,Subcollection,doi:1234/test,Survey 1,fr,Author,Producer,2020,"
            "France,,Individual,Contact,2020-01-01,https://example.com/xml/1234\n"
        )
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode(), content_type="text/csv")

        xml_content = """
        <root>
            <IDNo agency="DataCite">doi:1234/test</IDNo>
            <titl>Test</titl>
            <timePrd date="1982" event="start"/>
            <verStmt>
                <version date="2018-01-26">Version 1</version>
            </verStmt>
            <var name="Q1_1">
                <labl>Variant 1</labl>
                <qstn><qstnLit>Grid Question</qstnLit></qstn>
                <catgry>
                    <catValu>1</catValu>
                    <labl>Option 1</labl>
                    <catStat type="freq">10</catStat>
                </catgry>
            </var>
            <var name="Q1_2">
                <labl>Variant 2</labl>
                <qstn><qstnLit>Grid Question</qstnLit></qstn>
                <catgry>
                    <catValu>1</catValu>
                    <labl>Option 1</labl>
                    <catStat type="freq">10</catStat>
                </catgry>
            </var>
        </root>
        """

        mock_download.return_value = xml_content

        response = self.client.post(
            reverse("request_ddi:import_ddic"),
            {"csv_file": csv_file, "delimiter": ","},
        )

        # Wait for task to finish
        task_status, _ = wait_task()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertEqual(task_status, TaskResultStatus.SUCCESSFUL)
        self.assertTrue(Survey.objects.filter(external_ref="doi:1234/test").exists())
        self.assertEqual(len(RepresentedVariable.objects.all()), 2)

    @patch("request_ddi.core.parser.download_xml_file")
    def test_csv_with_question_text_label_from_multiple_surveys(self, mock_download):
        """Test when multiple surveys use same question text and label documentation"""
        self.login()

        csv_content = (
            "distributor,collection,sub_collection,doi,title,xml_lang,author,producer,start_date,"
            "geographic_coverage,geographic_unit,unit_of_analysis,contact,date_last_version,url\n"
            "Distrib,Collection,Subcollection,doi:1234/test,Survey 1,fr,Author,Producer,2020,"
            "France,,Individual,Contact,2020-01-01,https://example.com/xml/1234\n"
            "Distrib,Collection,Subcollection,doi:5678/test,Survey 2,fr,Author,Producer,2021,"
            "France,,Individual,Contact,2021-01-01,https://example.com/xml/5678\n"
        )
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode(), content_type="text/csv")

        xml_content_1 = """
        <root>
            <IDNo agency="DataCite">doi:1234/test</IDNo>
            <titl>Test</titl>
            <timePrd date="1982" event="start"/>
            <verStmt>
                <version date="2018-01-26">Version 1</version>
            </verStmt>
            <var name="Q12000">
                <labl>Variant 1</labl>
                <qstn><qstnLit>Grid Question</qstnLit></qstn>
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
            <titl>Test</titl>
            <timePrd date="1982" event="start"/>
            <verStmt>
                <version date="2018-01-26">Version 1</version>
            </verStmt>
            <var name="Q12001">
                <labl>Variant 1</labl>
                <qstn><qstnLit>Grid Question</qstnLit></qstn>
                <catgry>
                    <catValu>1</catValu>
                    <labl>Option 1</labl>
                    <catStat type="freq">20</catStat>
                </catgry>
            </var>
        </root>
        """

        mock_download.side_effect = lambda url: xml_content_1 if "1234" in url else xml_content_2

        response = self.client.post(
            reverse("request_ddi:import_ddic"),
            {"csv_file": csv_file, "delimiter": ","},
        )

        # Wait for task to finish
        task_status, _ = wait_task()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertEqual(task_status, TaskResultStatus.SUCCESSFUL)
        self.assertTrue(Survey.objects.filter(external_ref="doi:1234/test").exists())
        self.assertTrue(Survey.objects.filter(external_ref="doi:5678/test").exists())
        self.assertEqual(len(RepresentedVariable.objects.all()), 1)

    @patch("request_ddi.core.parser.download_xml_file")
    def test_csv_with_force_import(self, mock_download):
        """Test when CSV is force imported"""
        self.login()

        csv_content = (
            "distributor,collection,sub_collection,doi,title,xml_lang,author,producer,start_date,"
            "geographic_coverage,geographic_unit,unit_of_analysis,contact,date_last_version,url\n"
            "Distrib,Collection,Subcollection,doi:1234/test,Survey 1,fr,Author,Producer,2020,"
            "France,,Individual,Contact,2020-01-01,https://example.com/xml/1234\n"
        )
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode(), content_type="text/csv")

        mock_download.return_value = """
        <root>
            <IDNo agency="DataCite">doi:1234/test</IDNo>
            <titl>Test</titl>
            <timePrd date="1982" event="start"/>
            <verStmt>
                <version date="2018-01-26">Version 1</version>
            </verStmt>
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

        response = self.client.post(
            reverse("request_ddi:import_ddic"),
            {"csv_file": csv_file, "delimiter": ","},
        )

        # Wait for task to finish
        task_status, _ = wait_task()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertEqual(task_status, TaskResultStatus.SUCCESSFUL)
        self.assertTrue(Survey.objects.filter(external_ref="doi:1234/test").exists())

        # Make another request with force_import
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode(), content_type="text/csv")
        response = self.client.post(
            reverse("request_ddi:import_ddic"),
            {"csv_file": csv_file, "delimiter": ",", "force_import": "on"},
        )

        # Wait for task to finish
        task_status, _ = wait_task()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertEqual(task_status, TaskResultStatus.SUCCESSFUL)
        self.assertTrue(Survey.objects.filter(external_ref="doi:1234/test").exists())

    @patch("request_ddi.core.parser.download_xml_file")
    def test_malformed_xml_db_rollback(self, mock_download):
        """Test when variables in XML raise an exception which should rollback DB transcation"""
        self.login()

        csv_content = (
            "distributor,collection,sub_collection,doi,title,xml_lang,author,producer,start_date,"
            "geographic_coverage,geographic_unit,unit_of_analysis,contact,date_last_version,url\n"
            "Distrib,Collection,Subcollection,doi:1234/test,Survey 1,fr,Author,Producer,2020,"
            "France,,Individual,Contact,2020-01-01,https://example.com/xml/1234\n"
        )
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode(), content_type="text/csv")

        # Two variables with same name
        xml_content = """
        <root>
            <IDNo agency="DataCite">doi:1234/test</IDNo>
            <titl>Test</titl>
            <timePrd date="1982" event="start"/>
            <verStmt>
                <version date="2018-01-26">Version 1</version>
            </verStmt>
            <var name="Q1">
                <labl>Question 1</labl>
                <qstn><qstnLit>Text 1</qstnLit></qstn>
                <catgry>
                    <catValu>1</catValu>
                    <labl>Option 1</labl>
                    <catStat type="freq">10</catStat>
                </catgry>
            </var>
            <var name="Q1">
                <labl>Question 2</labl>
                <qstn><qstnLit>Text 2</qstnLit></qstn>
                <catgry>
                    <catValu>1</catValu>
                    <labl>Option 1</labl>
                    <catStat type="freq">10</catStat>
                </catgry>
            </var>
        </root>
        """

        mock_download.return_value = xml_content

        response = self.client.post(
            reverse("request_ddi:import_ddic"),
            {"csv_file": csv_file, "delimiter": ","},
        )

        # Wait for task to finish
        task_status, traceback = wait_task()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertEqual(task_status, TaskResultStatus.FAILED)
        self.assertFalse(Survey.objects.filter(external_ref="doi:1234/test").exists())
        self.assertIn("DataValidationError", traceback)

    @patch("request_ddi.core.parser.download_xml_file")
    def test_malformed_start_date_xml(self, mock_download):
        """Test when start_date in XML is not well formatted"""
        self.login()

        csv_content = (
            "distributor,collection,sub_collection,doi,title,xml_lang,author,producer,start_date,"
            "geographic_coverage,geographic_unit,unit_of_analysis,contact,date_last_version,url\n"
            "Distrib,Collection,Subcollection,doi:1234/test,Survey 1,fr,Author,Producer,2020,"
            "France,,Individual,Contact,2020-01-01,https://example.com/xml/1234\n"
        )
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode(), content_type="text/csv")

        # Two variables with same name
        mock_download.return_value = """
        <root>
            <IDNo agency="DataCite">doi:1234/test</IDNo>
            <titl>Test</titl>
            <timePrd date="19820101" event="start"/>
            <verStmt>
                <version date="2018-01-26">Version 1</version>
            </verStmt>
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

        response = self.client.post(
            reverse("request_ddi:import_ddic"),
            {"csv_file": csv_file, "delimiter": ","},
        )

        # Wait for task to finish
        task_status, traceback = wait_task()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertEqual(task_status, TaskResultStatus.FAILED)
        self.assertFalse(Survey.objects.filter(external_ref="doi:1234/test").exists())
        self.assertIn("InvalidDateError", traceback)

    @patch("request_ddi.core.parser.download_xml_file")
    def test_malformed_date_last_version_xml(self, mock_download):
        """Test when start_date in XML is not well formatted"""
        self.login()

        csv_content = (
            "distributor,collection,sub_collection,doi,title,xml_lang,author,producer,start_date,"
            "geographic_coverage,geographic_unit,unit_of_analysis,contact,date_last_version,url\n"
            "Distrib,Collection,Subcollection,doi:1234/test,Survey 1,fr,Author,Producer,2020,"
            "France,,Individual,Contact,2020-01-01,https://example.com/xml/1234\n"
        )
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode(), content_type="text/csv")

        # Two variables with same name
        mock_download.return_value = """
        <root>
            <IDNo agency="DataCite">doi:1234/test</IDNo>
            <titl>Test</titl>
            <timePrd date="1982-01-01" event="start"/>
            <verStmt>
                <version date="20180126">Version 1</version>
            </verStmt>
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

        response = self.client.post(
            reverse("request_ddi:import_ddic"),
            {"csv_file": csv_file, "delimiter": ","},
        )

        # Wait for task to finish
        task_status, traceback = wait_task()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertEqual(task_status, TaskResultStatus.FAILED)
        self.assertFalse(Survey.objects.filter(external_ref="doi:1234/test").exists())
        self.assertIn("InvalidDateError", traceback)


class CheckDuplicatesTest(MockElasticsearchMixin, BaseUploadTest):
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

    @patch("request_ddi.core.parser.download_xml_file")
    def test_check_duplicates_with_duplicate(self, mock_download):
        self.login()

        mock_download.return_value = """
        <root>
            <var name="Q1"/>
        </root>
        """

        csv_content = (
            "distributor;collection;sub_collection;doi;title;xml_lang;author;producer;start_date;"
            "geographic_coverage;geographic_unit;unit_of_analysis;contact;date_last_version;url\n"
            "Distrib;Collection;Subcollection;doi:1234/test;Survey Test;fr;Author;Producer;2020;"
            "France;;Individual;Contact;2020-01-01;https://example.com/xml/\n"
        )
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode(), content_type="text/csv")

        response = self.client.post(reverse("request_ddi:import_ddic"), {"csv_file": csv_file})
        self.assertEqual(response.status_code, 207)
        json_response = response.json()
        self.assertEqual(json_response["status"], "partial_success")
        self.assertTrue(any("doi:1234/test" in e for e in json_response["errors"]))

    @patch("request_ddi.core.parser.download_xml_file")
    def test_check_duplicates_with_no_duplicate(self, mock_download):
        self.login()

        mock_download.return_value = """
            <root>
                <titl>Test</titl>
                <timePrd date="1982" event="start"/>
                <verStmt>
                    <version date="2018-01-26">Version 1</version>
                </verStmt>
                <IDNo agency="DataCite">doi:9999/test</IDNo>
                <var name="Q1"/>
            </root>
            """

        csv_content = (
            "distributor;collection;sub_collection;doi;title;xml_lang;author;producer;start_date;"
            "geographic_coverage;geographic_unit;unit_of_analysis;contact;date_last_version;url\n"
            "Distrib;Collection;Subcollection;doi:9999/test;Survey Test;fr;Author;Producer;2020;"
            "France;;Individual;Contact;2020-01-01;https://example.com/xml/\n"
        )
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode(), content_type="text/csv")
        response = self.client.post(
            reverse("request_ddi:import_ddic"), {"csv_file": csv_file, "delimiter": ";"}
        )

        # Wait for task to finish
        task_status, _ = wait_task()

        self.assertEqual(response.status_code, 200)
        json_response = response.json()
        self.assertEqual(json_response["status"], "success")
        self.assertEqual(task_status, TaskResultStatus.SUCCESSFUL)
        self.assertEqual(Survey.objects.filter(external_ref="doi:9999/test").count(), 1)
