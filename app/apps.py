from django.apps import AppConfig
from health_check.plugins import plugin_dir

from .health_checks import ElasticsearchHealthCheck


class AppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app"

    def ready(self):
        # -- BASEDEQUESTIONS
        # IMPORTANT: This is needed for instantiation of signals
        # without which model changes won't automatically be pushed to ES
        import app.signals  # noqa: PLC0415, F401

        # enregistrer le custom health check Elasticsearch
        plugin_dir.register(ElasticsearchHealthCheck)
