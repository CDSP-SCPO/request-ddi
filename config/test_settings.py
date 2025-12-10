from .settings import *  # noqa: F403

SECRET_KEY = "test"  # noqa: S105

DATABASES["default"] = {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}  # noqa: F405

LOGGING["loggers"]["performance"] = {  # noqa: F405
    "handlers": [],
    "level": "CRITICAL",
    "propagate": False,
}
