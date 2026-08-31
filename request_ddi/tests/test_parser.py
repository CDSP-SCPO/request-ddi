from io import BytesIO
from unittest.mock import patch

from django.test import TestCase

from request_ddi.core.exceptions import (
    DDICFileURLNotFoundError,
    InvalidDDICError,
    InvalidDOIError,
    MissingAttributeError,
)
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


class XMLFetcherTests(TestCase):
    def test_fetch_xml_with_no_url(self):
        """Test when survey DDIC URL not found"""
        data = {"url": "", "doi": "doi:9999/test"}
        with self.assertRaises(DDICFileURLNotFoundError):
            fetch_and_parse_xml(data)

    @patch("request_ddi.core.parser.download_xml_file")
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
