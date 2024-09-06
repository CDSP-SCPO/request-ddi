from django.urls import path
from .views import CSVUploadView, RepresentedVariableSearchView, search_results, search_results_data
from django.views.generic import TemplateView

app_name = 'app'

urlpatterns = [
    path('upload-csv/', CSVUploadView.as_view(), name='upload_csv'),
    path('', RepresentedVariableSearchView.as_view(), name='representedvariable_search'),
    path('search-results/', search_results, name='search_results'),  
    path('api/search-results/', search_results_data, name='search_results_data'),
]

