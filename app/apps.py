# -- DJANGO
from django.apps import AppConfig


class AppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app"

    def ready(self):
        # -- BASEDEQUESTIONS
        # IMPORTANT: This is need for instantiation of signals
        # without which the changes to models in DB will not be
        # automatically made on the elastic search
        import app.signals  # noqa: PLC0415, F401
