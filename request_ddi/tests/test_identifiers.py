from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from request_ddi.core.exceptions import (
    InvalidDOIError,
    UnsupportedDDISchemaError,
)
from request_ddi.core.identifiers import is_doi, is_local_id, is_valid_survey_id
from request_ddi.core.models import Survey
from request_ddi.core.parser import (
    DDI_SCHEMA_CODEBOOK,
    DDI_SCHEMA_LIFECYCLE,
    detect_ddi_schema,
    extract_id_from_xml,
    fetch_and_parse_xml,
    parse_codebook_xml_file,
)


class IdentifierTests(SimpleTestCase):
    def test_valid_ids(self):
        self.assertTrue(is_valid_survey_id("doi:10.1234/test"))
        self.assertTrue(is_valid_survey_id("local:request/ENEF2017"))

    def test_invalid_local_ids(self):
        for bad in (
            "local:request/",
            "local:request/with space",
            "local:request/with-hyphen",
            "local:request/with_underscore",
            "local:other/abc",
            "ENEF2017",
            "",
            None,
        ):
            self.assertFalse(is_valid_survey_id(bad), bad)

    def test_is_doi_and_is_local_id_are_exclusive(self):
        self.assertTrue(is_doi("doi:10.1/x"))
        self.assertFalse(is_local_id("doi:10.1/x"))
        self.assertTrue(is_local_id("local:request/abc"))
        self.assertFalse(is_doi("local:request/abc"))

    def test_survey_has_doi(self):
        self.assertTrue(Survey(external_ref="doi:10.1/x").has_doi)
        self.assertFalse(Survey(external_ref="local:request/abc").has_doi)


class DDISchemaTests(TestCase):
    CODEBOOK = (
        '<codeBook xmlns="ddi:codebook:2_5"><IDNo>{id}</IDNo><titl>T</titl>'
        '<var name="Q1"><labl>L</labl><qstnLit>Q ?</qstnLit></var></codeBook>'
    )

    def test_detects_codebook_namespace(self):
        self.assertEqual(detect_ddi_schema(self.CODEBOOK.format(id="doi:1/a")), DDI_SCHEMA_CODEBOOK)

    def test_detects_lifecycle_namespace(self):
        xml = '<DDIInstance xmlns="ddi:instance:3_3"/>'
        self.assertEqual(detect_ddi_schema(xml), DDI_SCHEMA_LIFECYCLE)

    def test_lifecycle_import_is_not_supported_yet(self):
        with (
            self.assertRaises(UnsupportedDDISchemaError),
            patch(
                "request_ddi.core.parser.fetch_xml_from_remote",
                return_value='<DDIInstance xmlns="ddi:instance:3_3"/>',
            ),
        ):
            fetch_and_parse_xml({"id": "doi:1/a", "url": "https://example.com/x.xml"})

    def test_local_id_is_parsed_and_extracted(self):
        xml = self.CODEBOOK.format(id="local:request/ENEF2017")
        self.assertEqual(parse_codebook_xml_file(xml)["id"], "local:request/ENEF2017")
        self.assertEqual(extract_id_from_xml(xml), "local:request/ENEF2017")

    def test_invalid_local_id_is_rejected(self):
        with self.assertRaises(InvalidDOIError):
            parse_codebook_xml_file(self.CODEBOOK.format(id="local:request/ENEF-2017"))
