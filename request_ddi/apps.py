from django.apps import AppConfig
from health_check.plugins import plugin_dir

from .health_checks import ElasticsearchHealthCheck
from .utils.db_logging import DBQueryLogger


class AppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "request_ddi"
    verbose_name = "re{quest"

    def ready(self):
        # -- REQUEST_DDI
        # IMPORTANT: This is needed for instantiation of signals
        # without which model changes won't automatically be pushed to ES
        import request_ddi.core.signals  # noqa: PLC0415, F401

        # enregistrer le custom health check Elasticsearch
        plugin_dir.register(ElasticsearchHealthCheck)

        db_logger = DBQueryLogger()
        db_logger.enable()
