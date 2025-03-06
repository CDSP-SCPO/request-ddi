# -- DJANGO
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

# -- BASEDEQUESTIONS (LOCAL)
from .views import (
    CSVUploadView, CustomLoginView, QuestionDetailView,
    RepresentedVariableSearchView, SearchResultsDataView, XMLUploadView,
    autocomplete, check_duplicates, export_page, search_results,
    similar_conceptual_variable_questions,
    similar_representative_variable_questions, CreateSerie, check_media_root, SerieSurveysView, get_surveys_by_series, create_distributor, get_distributor, CSVUploadViewCollection
)

from django.contrib.auth.views import LogoutView

app_name = 'app'

urlpatterns = [
    path('upload-csv/', CSVUploadView.as_view(), name='upload_csv'),
    path('upload-xml/', XMLUploadView.as_view(), name='upload_xml'),
    path('', RepresentedVariableSearchView.as_view(), name='representedvariable_search'),
    path('search-results/', search_results, name='search_results'),  
    path('api/search-results/', SearchResultsDataView.as_view(), name='search_results_data'),

    path('export-csv/', export_page, name='export_page'),

    path('question/<int:id>/', QuestionDetailView.as_view(), name='question_detail'),
    path('questions/similar_representative/<int:question_id>/', similar_representative_variable_questions, name='similar_representative'),
    path('questions/similar_conceptual/<int:question_id>/', similar_conceptual_variable_questions, name='similar_conceptual'),

    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('create-serie/', CreateSerie.as_view(), name='create-serie'),
    path('check-duplicates/', check_duplicates, name='check_duplicates'),
    path('check-media-root/', check_media_root),
    path('serie/<int:serie_id>/surveys/', SerieSurveysView.as_view(), name='serie_surveys'),

    path('api/get-surveys-by-series/', get_surveys_by_series, name='get_surveys_by_series'),
    path('add-distributor/', create_distributor, name='create_distributor'),
    path('get-distributors/', get_distributor, name='get_distributor'),

    path('upload-csv-collection/', CSVUploadViewCollection.as_view(), name='upload_csv_collection'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

