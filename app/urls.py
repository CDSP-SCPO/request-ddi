# -- DJANGO
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.views import LogoutView
from django.urls import path, include

from .views.auth_views import CustomLoginView
from .views.detail_views import QuestionDetailView
from .views.export_views import export_page
from .views.search_views import (
    RepresentedVariableSearchView,
    search_results,
)

# -- BASEDEQUESTIONS (LOCAL)
from .views.upload_views import CSVUploadViewCollection, XMLUploadView, check_duplicates
API_VERSION = getattr(settings, "API_VERSION", "v1")

app_name = "app"

urlpatterns = [
    # === Upload de fichiers ===
    path("upload-xml/", XMLUploadView.as_view(), name="upload_xml"),
    path(
        "upload-csv-collection/",
        CSVUploadViewCollection.as_view(),
        name="upload_csv_collection",
    ),
    path("check-duplicates/", check_duplicates, name="check_duplicates"),
    # === Recherche de variables représentées ===
    path(
        "", RepresentedVariableSearchView.as_view(), name="representedvariable_search"
    ),
    path("search-results/", search_results, name="search_results"),


    # === Export ===
    path("export-csv/", export_page, name="export_page"),
    # === Détail des questions et similaires ===
    path("question/<int:id_quest>/", QuestionDetailView.as_view(), name="question_detail"),
    # === Authentification ===
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),


]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
