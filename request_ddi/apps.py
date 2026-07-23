from django.apps import AppConfig
from django.conf import settings

from .utils.db_logging import DBQueryLogger
from .utils.normalize_string import normalize_string_for_comparison


def register_collations(conn):
    try:

        def collate_und_ks_level1(x, y):
            return (
                0 if normalize_string_for_comparison(x) == normalize_string_for_comparison(y) else 1
            )

        conn.create_collation(
            "request_ddi_case_accent_insensitive_collation", collate_und_ks_level1
        )
    except Exception:  # noqa: S110
        pass


class AppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "request_ddi"
    verbose_name = "re{quest"

    def ready(self):
        # -- REQUEST_DDI
        # IMPORTANT: This is needed for instantiation of signals
        # without which model changes won't automatically be pushed to ES
        import request_ddi.core.signals  # noqa: PLC0415, F401

        db_logger = DBQueryLogger()
        db_logger.enable()

        # Just for unit tests. ICU based collations are available by default in PostgreSQL
        # but not in SQLite. We need to compile SQLite from sources using correct
        # compile flags to get ICU extensions which is an overkill for testing scenario.
        # So, we register custom Python function as a new collation and we test it.
        # It is important to test collation behavior as it is the crux of the logic on
        # how to link variables to represented variables.
        if "sqlite" in settings.DATABASES["default"]["ENGINE"]:
            from django.db import connections  # noqa: PLC0415
            from django.db.backends.signals import connection_created  # noqa: PLC0415

            # register for all *future* connections
            connection_created.connect(
                lambda sender, connection, **kwargs: register_collations(connection.connection),
                weak=False,
            )

            # also loop over all *existing* connections and register immediately
            for conn in connections.all():
                try:
                    register_collations(conn.connection)
                except Exception:  # noqa: S110
                    pass
