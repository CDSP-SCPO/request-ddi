from io import BytesIO

from django.test import TestCase

from request_ddi.core.parser import parse_codebook_xml_file


class XMLParserTests(TestCase):
    def test_parse_valid_xml(self):
        xml_content = """
        <root>
            <IDNo agency="DataCite">doi:10.1234/test</IDNo>
            <var name="Q1">
                <labl>Age</labl>
                <qstnLit>Quel âge avez-vous ?</qstnLit>
                <catgry>
                    <catValu>1</catValu><labl>18-25</labl><catStat type="freq">26</catStat>
                </catgry>
            </var>
        </root>
        """.encode()
        file = BytesIO(xml_content)
        file.name = "valid.xml"

        data = parse_codebook_xml_file(file)
        self.assertIsNotNone(data)
        self.assertEqual(len(data["variables"]), 1)
        self.assertEqual(data["doi"], "doi:10.1234/test")

    def test_parse_invalid_doi(self):
        xml_content = b"""
        <root>
            <IDNo>invalid_doi</IDNo>
            <var name="Q1"><labl>Test</labl></var>
        </root>
        """
        file = BytesIO(xml_content)
        file.name = "invalid.xml"

        data = parse_codebook_xml_file(file)

        self.assertIsNone(data)
