# -- STDLIB
import os
from pathlib import Path

# -- THIRDPARTY
from dotenv import load_dotenv

# ---------------------------------------------------------
# BASE DIRECTORY
# ---------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(os.path.join(BASE_DIR, ".env"))

# ---------------------------------------------------------
# DEBUG & SECRET
# ---------------------------------------------------------
DEBUG = os.getenv("DJANGO_DEBUG") == "True"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")

# ---------------------------------------------------------
# ALLOWED HOSTS
# ---------------------------------------------------------
ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

# ---------------------------------------------------------
# DATABASE
# ---------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB"),
        "USER": os.getenv("POSTGRES_USER"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD"),
        "HOST": os.getenv("POSTGRES_HOST"),
        "PORT": os.getenv("POSTGRES_PORT"),
    }
}

# ---------------------------------------------------------
# ELASTICSEARCH
# ---------------------------------------------------------
ELASTICSEARCH_HOST = os.getenv("ELASTICSEARCH_HOST")
ELASTICSEARCH_ADMIN_USER = os.getenv("ELASTICSEARCH_ADMIN_USER")
ELASTICSEARCH_ADMIN_PASSWORD = os.getenv("ELASTICSEARCH_ADMIN_PASSWORD")


ELASTICSEARCH_DSL = {
    "default": {
        "hosts": ELASTICSEARCH_HOST,
        "http_auth": (ELASTICSEARCH_ADMIN_USER, ELASTICSEARCH_ADMIN_PASSWORD),
    },
    "auto_sync": False,
}


# ---------------------------------------------------------
# APPLICATIONS & MIDDLEWARE
# ---------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_extensions",
    "django_elasticsearch_dsl",
    "app",
    "health_check",
    "health_check.db",
    "health_check.cache",
    "health_check.storage",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "basedequestions.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "app.context_processors.api_version",
            ],
        },
    },
]

WSGI_APPLICATION = "basedequestions.wsgi.application"

# ---------------------------------------------------------
# PASSWORD VALIDATION
# ---------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------
# INTERNATIONALIZATION
# ---------------------------------------------------------
LANGUAGE_CODE = "fr"
LANGUAGE_COOKIE_NAME = "django_language"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True

LANGUAGES = [("fr", "Français"), ("en", "English")]
LOCALE_PATHS = [os.path.join(BASE_DIR, "locale")]

# ---------------------------------------------------------
# STATIC & MEDIA
# ---------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "collected_static"
STATICFILES_DIRS = [BASE_DIR / "static"]

STATICFILES_STORAGE = (
    "django.contrib.staticfiles.storage.StaticFilesStorage"
    if DEBUG
    else "whitenoise.storage.CompressedManifestStaticFilesStorage"
)

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------
# CSRF / SECURITY
# ---------------------------------------------------------
CSRF_COOKIE_SECURE = not DEBUG
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "http://localhost:8000").split(",") if o.strip()]

# ---------------------------------------------------------
# LOGIN URLS
# ---------------------------------------------------------
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# ---------------------------------------------------------
# LOGGING
# ---------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{levelname} {asctime} {module} {message}", "style": "{"},
        "simple": {"format": "{levelname} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"level": "DEBUG", "class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO"},
        "app": {"handlers": ["console"], "level": "DEBUG"},
    },
}

if not DEBUG:
    LOGGING["handlers"]["file"] = {
        "level": "ERROR",
        "class": "logging.handlers.RotatingFileHandler",
        "filename": "errors.log",
        "maxBytes": 1024 * 1024 * 5,
        "backupCount": 5,
        "formatter": "simple",
    }
    LOGGING["handlers"]["mail_admins"] = {
        "level": "ERROR",
        "class": "django.utils.log.AdminEmailHandler",
        "include_html": False,
    }
    LOGGING["loggers"]["django"]["handlers"] = ["file", "mail_admins"]
    LOGGING["loggers"]["app"]["handlers"] = ["file", "mail_admins"]
    LOGGING["loggers"]["django"]["level"] = "ERROR"
    LOGGING["loggers"]["app"]["level"] = "ERROR"

# ---------------------------------------------------------
# HEALTH CHECKS
# ---------------------------------------------------------
HEALTH_CHECKS = ["app.health_checks.ElasticsearchHealthCheck"]

# ---------------------------------------------------------
# DEFAULT PK
# ---------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

API_VERSION = "v1"
