from django.urls import path
from .views import CSVUploadView, XMLUploadView, CombinedUploadView, RepresentedVariableSearchView, search_results, search_results_data, autocomplete, ExportQuestionsView, QuestionDetailView, similar_representative_variable_questions, similar_conceptual_variable_questions


app_name = 'app'

urlpatterns = [
    path('upload/', CombinedUploadView.as_view(), name='combined_upload'),
    path('upload-csv/', CSVUploadView.as_view(), name='upload_csv'),
    path('upload-xml/', XMLUploadView.as_view(), name='upload_xml'),
    path('', RepresentedVariableSearchView.as_view(), name='representedvariable_search'),
    path('search-results/', search_results, name='search_results'),  
    path('api/search-results/', search_results_data, name='search_results_data'),

    path('export-csv/', ExportQuestionsView.as_view(), name='export_page'),

    path('question/<int:id>/', QuestionDetailView.as_view(), name='question_detail'),

    path('questions/similar_representative/<int:question_id>/', similar_representative_variable_questions, name='similar_representative'),
    path('questions/similar_conceptual/<int:question_id>/', similar_conceptual_variable_questions, name='similar_conceptual'),
]

