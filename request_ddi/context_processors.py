from django.conf import settings


def api_version(request):
    return {"API_VERSION": getattr(settings, "API_VERSION", "v1")}
