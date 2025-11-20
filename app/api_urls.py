from django.urls import path
from django.conf import settings

from .views.filter_views import get_subcollections_by_collections, get_surveys_by_subcollections, get_decades, \
    get_years_by_decade

from .views.search_views import SearchResultsDataView

app_name = "api"

API_VERSION = getattr(settings, "API_VERSION", "v1")

urlpatterns = [
    # The `get_surveys_by_collections` endpoint has been removed
    # because surveys are now loaded based on subcollections instead of collections.

    path(
        f"{API_VERSION}/search-results/",
        SearchResultsDataView.as_view(),
        name="search_results_data",
    ),
    path(
        f"{API_VERSION}/get-subcollections-by-collections/",
        get_subcollections_by_collections,
        name="get_subcollections_by_collections",
    ),
    path(
        f"{API_VERSION}/get-surveys-by-subcollections/",
        get_surveys_by_subcollections,
        name="get_surveys_by_subcollections",
    ),

    path(f"{API_VERSION}/get-decades/", get_decades, name="get_decades"),
    path(f"{API_VERSION}/get-years-by-decade/", get_years_by_decade, name="get_years_by_decade"),

]
