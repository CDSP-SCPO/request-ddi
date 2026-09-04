from io import BytesIO
from unittest.mock import patch

from django.test import TestCase

from request_ddi.core.exceptions import (
    DDIXMLFileNotFoundError,
    InvalidDDICError,
    InvalidDOIError,
    MissingAttributeError,
)
from request_ddi.core.models import UploadedDDIXMLFile
from request_ddi.core.parser import (
    fetch_and_parse_xml,
    parse_codebook_xml_file,
)


class XMLParserTests(TestCase):
    def test_parse_valid_xml(self):
        xml_content = """
        <codeBook version="1.2.2" ID="doi:10.1234/test" xml-lang="en">
            <IDNo agency="DataCite">doi:10.1234/test</IDNo>
            <titl>Test</titl>
            <timePrd date="1982" event="start"/>
            <verStmt>
                <version date="2018-01-26">Version 1</version>
            </verStmt>
            <rspStmt>
                <AuthEnty affiliation="aff1">surname1, name1</AuthEnty>
                <AuthEnty affiliation="aff2">surname2, name2</AuthEnty>
            </rspStmt>
            <var name="Q1">
                <labl>Age</labl>
                <qstnLit>Quel âge avez-vous ?</qstnLit>
                <catgry>
                    <catValu>1</catValu><labl>18-25</labl><catStat type="freq">26</catStat>
                </catgry>
            </var>
        </codeBook>
        """.encode()
        file = BytesIO(xml_content)
        file.name = "valid.xml"

        data = parse_codebook_xml_file(file)
        self.assertIsNotNone(data)
        self.assertEqual(len(data["variables"]), 1)
        self.assertEqual(data["doi"], "doi:10.1234/test")
        self.assertEqual(data["lang"], "en")
        self.assertEqual(data["authors"], "surname1, name1 (aff1); surname2, name2 (aff2)")

    def test_parse_invalid_doi(self):
        xml_content = b"""
        <root>
            <IDNo>invalid_doi</IDNo>
            <var name="Q1"><labl>Test</labl></var>
        </root>
        """
        file = BytesIO(xml_content)
        file.name = "invalid.xml"

        with self.assertRaises(InvalidDOIError):
            parse_codebook_xml_file(file)

    def test_parse_invalid_xml_missing_title(self):
        xml_content = """
        <codeBook version="1.2.2" ID="doi:10.1234/test" xml-lang="en">
            <IDNo agency="DataCite">doi:10.1234/test</IDNo>
            <timePrd date="1982" event="start"/>
            <verStmt>
                <version date="2018-01-26">Version 1</version>
            </verStmt>
            <rspStmt>
                <AuthEnty affiliation="aff1">surname1, name1</AuthEnty>
                <AuthEnty affiliation="aff2">surname2, name2</AuthEnty>
            </rspStmt>
            <var name="Q1">
                <labl>Age</labl>
                <qstnLit>Quel âge avez-vous ?</qstnLit>
                <catgry>
                    <catValu>1</catValu><labl>18-25</labl><catStat type="freq">26</catStat>
                </catgry>
            </var>
        </codeBook>
        """.encode()
        file = BytesIO(xml_content)
        file.name = "invalid.xml"

        with self.assertRaises(MissingAttributeError):
            parse_codebook_xml_file(file)

    def test_parse_invalid_xml_no_variables(self):
        xml_content = """
        <codeBook version="1.2.2" ID="doi:10.1234/test" xml-lang="en">
            <IDNo agency="DataCite">doi:10.1234/test</IDNo>
            <titl>Résultats agrégés sans variable</titl>
        </codeBook>
        """.encode()
        file = BytesIO(xml_content)
        file.name = "no-variables.xml"

        with self.assertRaises(MissingAttributeError):
            parse_codebook_xml_file(file)


class XMLFetcherTests(TestCase):
    def test_fetch_xml_with_no_url_and_no_uploaded_file(self):
        """Test when survey has no URL and no XML was uploaded to the volume for its DOI"""
        data = {"url": "", "doi": "doi:9999/test"}
        with self.assertRaises(DDIXMLFileNotFoundError):
            fetch_and_parse_xml(data)

    def test_fetch_xml_with_no_url_reads_from_volume(self):
        """Test when survey has no URL but a matching XML was uploaded to the volume"""
        xml_content = """
        <codeBook version="1.2.2" ID="doi:9999/test" xml-lang="fr">
            <IDNo agency="DataCite">doi:9999/test</IDNo>
            <titl>Test depuis le volume</titl>
            <timePrd date="1982" event="start"/>
            <verStmt>
                <version date="2018-01-26">Version 1</version>
            </verStmt>
            <var name="Q1"><labl>Age</labl></var>
        </codeBook>
        """
        UploadedDDIXMLFile.objects.create(
            doi="doi:9999/test",
            original_filename="test.xml",
            xml_content=xml_content,
        )

        data = fetch_and_parse_xml({"url": "", "doi": "doi:9999/test"})

        self.assertEqual(data["title"], "Test depuis le volume")

    @patch("request_ddi.core.parser.fetch_xml_from_remote")
    def test_fetch_xml_with_mismatching_dois(self, mock_download):
        """Test when survey DDIC DOI does not match with DOI in CSV"""
        data = {"url": "https://example.com/1", "doi": "doi:9999/test"}

        mock_download.return_value = """
        <root>
            <titl>Test</titl>
            <timePrd date="1982" event="start"/>
            <verStmt>
                <version date="2018-01-26">Version 1</version>
            </verStmt>
            <IDNo agency="DataCite">doi:9998/test</IDNo>
            <var name="Q1"/>
        </root>
        """

        with self.assertRaises(InvalidDDICError):
            fetch_and_parse_xml(data)
