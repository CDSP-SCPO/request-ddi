from django.test import TestCase

from app.views.utils_views import remove_html_tags


class RemoveHTMLTagsTest(TestCase):
    def test_remove_html_tags(self):
        """Teste la suppression des balises HTML."""
        self.assertEqual(remove_html_tags("<p>Test</p>"), "Test")
        self.assertEqual(remove_html_tags("Pas de balise"), "Pas de balise")
        self.assertEqual(remove_html_tags("<div><span>Test</span></div>"), "Test")
