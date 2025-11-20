from io import BytesIO

from django.test import TestCase

from app.parser import XMLParser  # adapte le chemin selon ton projet


class XMLParserTests(TestCase):
    def setUp(self):
        self.parser = XMLParser()

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

        seen_invalid_dois = set()
        data = self.parser.parse_file(file, seen_invalid_dois)
        self.assertIsNotNone(data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0][0], "doi:10.1234/test")
        self.assertEqual(self.parser.errors, [])

    def test_parse_invalid_doi(self):
        xml_content = b"""
        <root>
            <IDNo>invalid_doi</IDNo>
            <var name="Q1"><labl>Test</labl></var>
        </root>
        """
        file = BytesIO(xml_content)
        file.name = "invalid.xml"

        seen_invalid_dois = set()
        data = self.parser.parse_file(file, seen_invalid_dois)

        self.assertIsNone(data)
        self.assertTrue(any("DOI invalide" in e for e in self.parser.errors))
