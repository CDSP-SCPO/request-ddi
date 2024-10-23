"""
WSGI config for basedequestions project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

# -- STDLIB
import os

# -- DJANGO
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'basedequestions.settings')

application = get_wsgi_application()
