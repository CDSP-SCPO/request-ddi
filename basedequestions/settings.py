from pathlib import Path
from get_docker_secret import get_docker_secret
import os
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Charger le fichier .env
load_dotenv(os.path.join(BASE_DIR, '.env'))

# Définir l'environnement : développement ou production (par défaut : production)
ENVIRONMENT = os.getenv('DJANGO_ENV', 'production')

# Clé secrète Django (utiliser des secrets pour la production)
if ENVIRONMENT == 'production':
    SECRET_KEY = get_docker_secret('DJANGO_SECRET_KEY', autocast_name=False)
else:
    SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'changeme-in-dev')

# Debug mode : activé uniquement en dev
DEBUG = os.getenv('DJANGO_DEBUG', 'False') == 'True'

# Hôtes autorisés (en production, utiliser des domaines spécifiques)
if ENVIRONMENT == 'production':
    ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '').split(',')
else:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']

# Elasticsearch host
ELASTICSEARCH_HOST = os.getenv('ELASTICSEARCH_HOST', 'localhost:9200')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Elasticsearch
    'django_elasticsearch_dsl',
    # Your app
    'app',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'basedequestions.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'basedequestions.wsgi.application'


# Database configuration : utiliser les variables d'environnement
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB'),
        'USER': os.getenv('POSTGRES_USER'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD'),
        'HOST': os.getenv('POSTGRES_HOST', 'db'),
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'  # Vérifie qu'il a une barre oblique à la fin
STATIC_ROOT = os.path.join(BASE_DIR, 'collected_static')  # Dossier pour les fichiers collectés

if ENVIRONMENT == 'production':
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'  # Utilisé en production
else:
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'  # Utilisé en dev

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),  # Dossier pour les fichiers statiques de l'application
]

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Elasticsearch configuration
ELASTICSEARCH_DSL = {
    'default': {
        'hosts': ELASTICSEARCH_HOST,
    },
}

# Sécurités en production
if ENVIRONMENT == 'production':
    CSRF_TRUSTED_ORIGINS = os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')
    CSRF_COOKIE_SECURE = True
else:
    CSRF_COOKIE_SECURE = False
    CSRF_TRUSTED_ORIGINS = ["http://localhost:8000"]