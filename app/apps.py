from django.apps import AppConfig
from health_check.plugins import plugin_dir

class AppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app"

    def ready(self):
        # -- BASEDEQUESTIONS
        # IMPORTANT: This is need for instantiation of signals
        # without which the changes to models in DB will not be
        # automatically made on the elastic search
        import app.signals  # noqa: PLC0415, F401

        # enregistrer le custom health check Elasticsearch
        from .health_checks import ElasticsearchHealthCheck
        plugin_dir.register(ElasticsearchHealthCheck)

