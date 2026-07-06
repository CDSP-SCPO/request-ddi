from django.conf import settings

from ._version import __version__


def app_version(request):
    return {"APP_VERSION": __version__}


def api_version(request):
    return {"API_VERSION": getattr(settings, "API_VERSION", "v1")}
