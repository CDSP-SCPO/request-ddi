# -- DJANGO
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.views import LogoutView
from django.urls import path

from .views.auth_views import CustomLoginView
from .views.detail_views import QuestionDetailView
from .views.export_views import export_page
from .views.filter_views import (
    get_decades,
    get_subcollections_by_collections,
    get_surveys_by_collections,
    get_surveys_by_subcollections,
    get_years_by_decade,
)
from .views.search_views import (
    RepresentedVariableSearchView,
    SearchResultsDataView,
    search_results,
)

# -- BASEDEQUESTIONS (LOCAL)
from .views.upload_views import CSVUploadViewCollection, XMLUploadView, check_duplicates

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
    path(
        "api/search-results/",
        SearchResultsDataView.as_view(),
        name="search_results_data",
    ),
    # === Export ===
    path("export-csv/", export_page, name="export_page"),
    # === Détail des questions et similaires ===
    path("question/<int:id>/", QuestionDetailView.as_view(), name="question_detail"),
    # === Authentification ===
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    # === API - Données d'organisation (collections, sous-collections, enquêtes) ===
    path(
        "api/get-surveys-by-collections/",
        get_surveys_by_collections,
        name="get_surveys_by_collections",
    ),
    path(
        "api/get-subcollections-by-collections/",
        get_subcollections_by_collections,
        name="get_subcollections_by_collections",
    ),
    path(
        "api/get-surveys-by-subcollections/",
        get_surveys_by_subcollections,
        name="get_surveys_by_subcollections",
    ),
    # === API - Filtres temporels ===
    path("api/get-decades/", get_decades, name="get_decades"),
    path("api/get-years-by-decade/", get_years_by_decade, name="get_years_by_decade"),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
