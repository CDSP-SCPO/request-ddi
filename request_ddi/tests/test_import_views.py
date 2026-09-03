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
    UploadedDDICFile,
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


class DDICImportFromVolumeTest(MockElasticsearchMixin, BaseUploadTest):
    """Teste l'import CSV dont la colonne `url` est vide : le XML doit être retrouvé
    dans le volume (`UploadedDDICFile`) au lieu d'être téléchargé.
    """

    xml_content = """
        <root>
            <IDNo agency="DataCite">doi:1234/volume</IDNo>
            <titl>Survey From Volume</titl>
            <timePrd date="1982" event="start"/>
            <verStmt>
                <version date="2018-01-26">Version 1</version>
            </verStmt>
            <var name="Q1">
                <labl>Âge</labl>
                <qstnLit>Quel est votre âge ?</qstnLit>
            </var>
        </root>
        """

    def csv_with_empty_url(self, doi):
        content = (
            "distributor,collection,sub_collection,doi,title,xml_lang,author,producer,"
            "start_date,geographic_coverage,geographic_unit,unit_of_analysis,contact,"
            "date_last_version,url\n"
            f"Distrib,Collection,Subcollection,{doi},Survey Test,fr,Author,Producer,2020,"
            "France,,Individual,Contact,2020-01-01,\n"
        )
        return SimpleUploadedFile("test.csv", content.encode(), content_type="text/csv")

    def test_import_with_empty_url_and_uploaded_file_succeeds(self):
        self.login()
        UploadedDDICFile.objects.create(
            doi="doi:1234/volume",
            original_filename="survey.xml",
            xml_content=self.xml_content,
        )

        response = self.client.post(
            reverse("request_ddi:import_ddic"),
            {"csv_file": self.csv_with_empty_url("doi:1234/volume"), "delimiter": ","},
        )
        task_status, _ = wait_task()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertEqual(task_status, TaskResultStatus.SUCCESSFUL)
        self.assertTrue(Survey.objects.filter(external_ref="doi:1234/volume").exists())

        # La ligne est supprimée dès que l'import réussit, plus de trace en base
        self.assertFalse(UploadedDDICFile.objects.filter(doi="doi:1234/volume").exists())

    def test_force_import_without_new_upload_after_first_import_fails(self):
        """Une fois consommé par un premier import, un force_import sur ce DOI doit
        échouer exactement comme si aucun fichier n'avait jamais été déposé.
        """
        self.login()
        UploadedDDICFile.objects.create(
            doi="doi:1234/volume",
            original_filename="survey.xml",
            xml_content=self.xml_content,
        )
        self.client.post(
            reverse("request_ddi:import_ddic"),
            {"csv_file": self.csv_with_empty_url("doi:1234/volume"), "delimiter": ","},
        )
        wait_task()

        response = self.client.post(
            reverse("request_ddi:import_ddic"),
            {
                "csv_file": self.csv_with_empty_url("doi:1234/volume"),
                "delimiter": ",",
                "force_import": "on",
            },
        )
        task_status, traceback = wait_task()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(task_status, TaskResultStatus.FAILED)
        self.assertIn("Aucun fichier XML n'a été déposé", traceback)

    def test_import_survey_with_no_variables_fails(self):
        """Un DDI-C sans balise <var> (ex: un jeu de résultats agrégés sans variable
        documentée) doit être rejeté dès la validation du XML — même comportement
        que si ce fichier avait été récupéré par URL depuis data.sciencespo.
        """
        self.login()
        xml_content = """
            <root>
                <IDNo agency="DataCite">doi:1234/no-variables</IDNo>
                <titl>Résultats agrégés sans variable</titl>
            </root>
            """
        UploadedDDICFile.objects.create(
            doi="doi:1234/no-variables",
            original_filename="no-variables.xml",
            xml_content=xml_content,
        )

        response = self.client.post(
            reverse("request_ddi:import_ddic"),
            {"csv_file": self.csv_with_empty_url("doi:1234/no-variables"), "delimiter": ","},
        )
        task_status, traceback = wait_task()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(task_status, TaskResultStatus.FAILED)
        self.assertIn("Aucune variable", traceback)
        self.assertFalse(Survey.objects.filter(external_ref="doi:1234/no-variables").exists())

    def test_import_with_empty_url_and_no_uploaded_file_fails(self):
        self.login()

        response = self.client.post(
            reverse("request_ddi:import_ddic"),
            {"csv_file": self.csv_with_empty_url("doi:9999/missing"), "delimiter": ","},
        )
        task_status, traceback = wait_task()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertEqual(task_status, TaskResultStatus.FAILED)
        self.assertIn("Aucun fichier XML n'a été déposé", traceback)
        self.assertFalse(Survey.objects.filter(external_ref="doi:9999/missing").exists())


class DDICXMLUploadViewTest(BaseUploadTest):
    """Teste l'endpoint /import/xml de dépôt direct de fichiers XML dans le volume."""

    valid_xml = """
        <root>
            <IDNo agency="DataCite">doi:5555/upload</IDNo>
            <titl>Uploaded Survey</titl>
            <var name="Q1"><labl>Question 1</labl></var>
        </root>
        """

    def test_upload_valid_xml_creates_uploaded_file(self):
        self.login()
        xml_file = SimpleUploadedFile(
            "survey.xml", self.valid_xml.encode(), content_type="text/xml"
        )

        response = self.client.post(reverse("request_ddi:import_xml"), {"xml_files": xml_file})

        self.assertEqual(response.status_code, 200)
        json_response = response.json()
        self.assertEqual(json_response["status"], "success")
        self.assertEqual(json_response["data"][0]["dois"], ["doi:5555/upload"])

        uploaded = UploadedDDICFile.objects.get(doi="doi:5555/upload")
        self.assertEqual(uploaded.original_filename, "survey.xml")

    def test_upload_non_utf8_xml_is_decoded_correctly(self):
        """Un DDI-C encodé en ISO-8859-1 (courant sur d'anciens exports), déclarant
        son encodage dans le prologue XML, doit être décodé correctement plutôt que
        supposé UTF-8 à tort.
        """
        self.login()
        xml_content = """<?xml version="1.0" encoding="ISO-8859-1"?>
        <root>
            <IDNo agency="DataCite">doi:6666/latin1</IDNo>
            <titl>Enquête générationnelle âgée</titl>
            <var name="Q1"><labl>Question 1</labl></var>
        </root>
        """
        xml_file = SimpleUploadedFile(
            "survey.xml", xml_content.encode("iso-8859-1"), content_type="text/xml"
        )

        response = self.client.post(reverse("request_ddi:import_xml"), {"xml_files": xml_file})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

        uploaded = UploadedDDICFile.objects.get(doi="doi:6666/latin1")
        self.assertIn("Enquête générationnelle âgée", uploaded.xml_content)

    def test_upload_without_staff_permission_is_rejected(self):
        User.objects.create_user(username="not-staff", password="pwd")  # noqa: S106
        self.client.logout()
        self.client.login(username="not-staff", password="pwd")  # noqa: S106

        xml_file = SimpleUploadedFile(
            "survey.xml", self.valid_xml.encode(), content_type="text/xml"
        )
        response = self.client.post(reverse("request_ddi:import_xml"), {"xml_files": xml_file})

        self.assertNotEqual(response.status_code, 200)

    def test_upload_malformed_xml_is_rejected(self):
        self.login()
        malformed_xml = "<root><titl>No DOI here</titl></root>"
        xml_file = SimpleUploadedFile("bad.xml", malformed_xml.encode(), content_type="text/xml")

        response = self.client.post(reverse("request_ddi:import_xml"), {"xml_files": xml_file})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "error")
        self.assertFalse(UploadedDDICFile.objects.exists())

    def test_upload_xml_without_variables_is_rejected(self):
        self.login()
        no_variables_xml = """
            <root>
                <IDNo agency="DataCite">doi:7777/no-variables</IDNo>
                <titl>Résultats agrégés sans variable</titl>
            </root>
            """
        xml_file = SimpleUploadedFile(
            "no-variables.xml", no_variables_xml.encode(), content_type="text/xml"
        )

        response = self.client.post(reverse("request_ddi:import_xml"), {"xml_files": xml_file})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "error")
        self.assertFalse(UploadedDDICFile.objects.exists())

    def test_upload_non_xml_file_is_rejected(self):
        self.login()
        text_file = SimpleUploadedFile("notes.txt", b"hello", content_type="text/plain")

        response = self.client.post(reverse("request_ddi:import_xml"), {"xml_files": text_file})

        self.assertEqual(response.status_code, 400)
        self.assertTrue(any("format XML" in e for e in response.json()["errors"]))

    def test_upload_accepts_uppercase_xml_extension(self):
        self.login()
        xml_file = SimpleUploadedFile(
            "Survey.XML", self.valid_xml.encode(), content_type="text/xml"
        )

        response = self.client.post(reverse("request_ddi:import_xml"), {"xml_files": xml_file})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

    def test_upload_mixed_valid_and_invalid_files_is_partial_success(self):
        self.login()
        good_file = SimpleUploadedFile("good.xml", self.valid_xml.encode(), content_type="text/xml")
        bad_file = SimpleUploadedFile("bad.txt", b"hello", content_type="text/plain")

        response = self.client.post(
            reverse("request_ddi:import_xml"),
            {"xml_files": [good_file, bad_file]},
        )

        self.assertEqual(response.status_code, 207)
        self.assertEqual(response.json()["status"], "partial_success")
        self.assertEqual(UploadedDDICFile.objects.count(), 1)

    def test_upload_overwrites_existing_doi(self):
        self.login()
        existing = UploadedDDICFile.objects.create(
            doi="doi:5555/upload",
            original_filename="old.xml",
            xml_content=self.valid_xml,
        )

        xml_file = SimpleUploadedFile("new.xml", self.valid_xml.encode(), content_type="text/xml")
        response = self.client.post(reverse("request_ddi:import_xml"), {"xml_files": xml_file})

        self.assertEqual(response.status_code, 200)
        existing.refresh_from_db()
        self.assertEqual(existing.original_filename, "new.xml")

    def test_upload_no_file_returns_error(self):
        self.login()

        response = self.client.post(reverse("request_ddi:import_xml"), {})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "error")
