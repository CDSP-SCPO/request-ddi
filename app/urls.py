from django.urls import path
from .views import CSVUploadView, RepresentedVariableSearchView, survey_list_view, get_surveys
from django.views.generic import TemplateView

app_name = 'app'

urlpatterns = [
    path('upload-csv/', CSVUploadView.as_view(), name='upload_csv'),
    path('upload-success/', TemplateView.as_view(template_name='upload_success.html'), name='upload_success'),
    path('', RepresentedVariableSearchView.as_view(), name='representedvariable_search'),
    path('surveys/', survey_list_view, name='survey_list'),
    path('api/surveys/', get_surveys, name='get_surveys'),
]

