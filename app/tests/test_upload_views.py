from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from app.models import (
    BindingSurveyRepresentedVariable,
    Collection,
    ConceptualVariable,
    Distributor,
    RepresentedVariable,
    Subcollection,
    Survey,
)


class BaseUploadTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client = Client()


class XMLUploadViewTest(BaseUploadTest):
    def test_form_valid_with_valid_xml(self):
        """Teste l'import d'un fichier XML valide."""
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
                </catgry>
            </var>
        </root>
        """.encode()
        xml_file = SimpleUploadedFile("test.xml", xml_content, content_type="text/xml")

        with patch("app.views.upload_views.XMLUploadView.convert_data") as mock_convert:
            mock_convert.return_value = [{"variable_name": "Q1", "survey_id": "doi:1234/test"}]
            with patch("app.dataImporter.DataImporter.import_data") as mock_import:
                mock_import.return_value = (1, 1, 1)
                response = self.client.post(
                    reverse("app:upload_xml"),
                    {"xml_file": xml_file},
                    format="multipart/form-data"
                )
                self.assertEqual(response.status_code, 302)

    def test_form_invalid_with_invalid_xml(self):
        xml_content = b"<root></root>"
        xml_file = SimpleUploadedFile("test.xml", xml_content, content_type="text/xml")

        with patch("app.views.upload_views.XMLUploadView.convert_data", side_effect=ValueError("Erreur XML")):
            response = self.client.post(
                reverse("app:upload_xml"),
                {"xml_file": xml_file},
                format="multipart/form-data"
            )
            self.assertEqual(response.status_code, 200)


class CSVUploadViewCollectionTest(BaseUploadTest):
    def test_form_valid_with_valid_csv(self):
        csv_content = (
            "distributor,collection,sous-collection,doi,title,xml_lang,author,producer,start_date,"
            "geographic_coverage,geographic_unit,unit_of_analysis,contact,date_last_version\n"
            "Distrib,Collection,Subcollection,doi:1234/test,Survey Test,fr,Author,Producer,2020,France,,Individual,Contact,2020-01-01\n"
        )
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode(), content_type="text/csv")
        response = self.client.post(
            reverse("app:upload_csv_collection"),
            {"csv_file": csv_file, "delimiter": ","}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

    def test_form_invalid_with_duplicate_doi(self):
        """Teste l'import d'un fichier CSV avec un DOI en double."""
        Distributor.objects.create(name="Distrib")
        Collection.objects.create(name="Collection", distributor=Distributor.objects.first())
        Subcollection.objects.create(name="Subcollection", collection=Collection.objects.first())
        Survey.objects.create(
            external_ref="doi:1234/test",
            name="Survey Test",
            subcollection=Subcollection.objects.first()
        )

        csv_content = (
            "distributor,collection,sous-collection,doi,title,xml_lang,author,producer,start_date,"
            "geographic_coverage,geographic_unit,unit_of_analysis,contact,date_last_version\n"
            "Distrib,Collection,Subcollection,doi:1234/test,Survey Test,fr,Author,Producer,2020,France,,Individual,Contact,2020-01-01\n"
        )
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode(), content_type="text/csv")

        response = self.client.post(
            reverse("app:upload_csv_collection"),
            {"csv_file": csv_file, "delimiter": ","}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "error")


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
            variable_name="Q1",
            survey=cls.survey,
            variable=represented_var,
            notes="",
            universe=""
        )

    def test_check_duplicates_with_duplicate(self):
        xml_content = b"""
        <root>
            <IDNo agency="DataCite">doi:1234/test</IDNo>
            <var name="Q1"/>
        </root>
        """
        xml_file = SimpleUploadedFile("test.xml", xml_content, content_type="text/xml")
        response = self.client.post(reverse("app:check_duplicates"), {"xml_file": xml_file})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "exists")
        self.assertIn("Q1", response.json()["existing_variables"])

    def test_check_duplicates_with_no_duplicate(self):
        xml_content = b"""
        <root>
            <IDNo agency="DataCite">doi:1234/test</IDNo>
            <var name="Q2"/>
        </root>
        """
        xml_file = SimpleUploadedFile("test.xml", xml_content, content_type="text/xml")
        response = self.client.post(reverse("app:check_duplicates"), {"xml_file": xml_file})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "no_duplicates")
