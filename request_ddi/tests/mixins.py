from unittest.mock import MagicMock, patch


class MockElasticsearchMixin:
    """Mixin pour désactiver Elasticsearch dans les tests"""

    def setUp(self):
        super().setUp()

        # Mock le document ES appelé dans les signals
        self.es_patcher = patch("request_ddi.core.signals.BindingSurveyDocument")
        self.mock_es_doc = self.es_patcher.start()

        self.es_patcher_importer = patch("request_ddi.core.data_importer.BindingSurveyDocument")
        self.mock_es_doc_importer = self.es_patcher_importer.start()

        # Configurer le comportement du mock
        for mock in [self.mock_es_doc, self.mock_es_doc_importer]:
            mock_instance = MagicMock()
            mock.return_value = mock_instance
            mock_instance.update.return_value = None
            mock_instance.delete.return_value = None
            mock_instance._get_connection.return_value = MagicMock()

    def tearDown(self):
        self.es_patcher.stop()
        self.es_patcher_importer.stop()
        super().tearDown()
