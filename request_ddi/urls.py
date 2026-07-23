# -- DJANGO
from django.conf import settings
from django.contrib.auth.views import LogoutView
from django.urls import path
from health_check.views import HealthCheckView

from request_ddi.views.import_status import ImportRetryView, ImportStatusView

from .views.auth_views import CustomLoginView
from .views.detail_views import QuestionDetailView
from .views.export_views import export_page
from .views.search_views import (
    RepresentedVariableSearchView,
    search_results,
)

# -- REQUEST_DDI (LOCAL)
from .views.upload_views import CSVUploadViewCollection

API_VERSION = getattr(settings, "API_VERSION", "v1")

app_name = "request_ddi"

urlpatterns = [
    # === Upload de fichiers ===
    path(
        "import/",
        CSVUploadViewCollection.as_view(),
        name="import",
    ),
    # === Recherche de variables représentées ===
    path("", RepresentedVariableSearchView.as_view(), name="representedvariable_search"),
    path("search-results/", search_results, name="search_results"),
    # === Export ===
    path("export-csv/", export_page, name="export_page"),
    # === Détail des questions et similaires ===
    path("question/<int:id_quest>/", QuestionDetailView.as_view(), name="question_detail"),
    # === Authentification ===
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("import/status/", ImportStatusView.as_view(), name="import_status"),
    path("import/status/retry/", ImportRetryView.as_view(), name="import_retry"),
    path(
        "health/",
        HealthCheckView.as_view(
            checks=[
                "health_check.Cache",
                "health_check.Database",
                "health_check.Storage",
                # 3rd party checks
                "health_check.contrib.psutil.Disk",
                "health_check.contrib.psutil.Memory",
                # Custom checks
                "request_ddi.health_checks.ElasticsearchHealthCheck",
            ]
        ),
    ),
]
