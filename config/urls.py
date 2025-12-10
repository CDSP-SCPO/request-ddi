"""
URL configuration for request_ddi project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

# -- DJANGO
from django.contrib import admin
from django.urls import include, path
from django.views.i18n import set_language

# -- REQUEST_DDI
from request_ddi.views.export_views import ExportQuestionsCSVView

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    path("set_language/", set_language, name="set_language"),
    path("admin/", admin.site.urls),
    path("", include("request_ddi.urls")),
    path(
        "export/questions/",
        ExportQuestionsCSVView.as_view(),
        name="export_questions_csv",
    ),
    path("health/", include("health_check.urls")),
    # -------------------
    # API versionnée
    # -------------------
    path("api/", include(("request_ddi.api_urls", "api"), namespace="api")),
]
