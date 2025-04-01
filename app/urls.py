# -- DJANGO
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.views import LogoutView
from django.urls import path

# -- BASEDEQUESTIONS (LOCAL)
from .views import (
    CollectionSurveysView, CSVUploadView, CSVUploadViewCollection,
    CustomLoginView, QuestionDetailView, RepresentedVariableSearchView,
    SearchResultsDataView, SubcollectionSurveysView, XMLUploadView,
    check_duplicates, check_media_root, create_distributor, export_page,
    get_distributor, get_subcollections_by_collections,
    get_surveys_by_collections, get_surveys_by_subcollections, search_results,
    similar_conceptual_variable_questions,
    similar_representative_variable_questions,
)

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
    path('check-duplicates/', check_duplicates, name='check_duplicates'),
    path('check-media-root/', check_media_root),
    path('collection/<int:collection_id>/surveys/', CollectionSurveysView.as_view(), name='collection_subcollections'),

    path('api/get-surveys-by-collections/', get_surveys_by_collections, name='get_surveys_by_collections'),
    path('add-distributor/', create_distributor, name='create_distributor'),
    path('get-distributors/', get_distributor, name='get_distributor'),

    path('upload-csv-collection/', CSVUploadViewCollection.as_view(), name='upload_csv_collection'),

    path('subcollection/<int:subcollection_id>/', SubcollectionSurveysView.as_view(), name='subcollection_surveys'),

    path('api/get-subcollections-by-collections/', get_subcollections_by_collections, name='get_subcollections_by_collections'),
    path('api/get-surveys-by-subcollections/', get_surveys_by_subcollections, name='get_surveys_by_subcollections'),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

