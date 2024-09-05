from django.urls import path
from .views import CSVUploadView, RepresentedVariableSearchView
from django.views.generic import TemplateView

app_name = 'app'

urlpatterns = [
    path('upload-csv/', CSVUploadView.as_view(), name='upload_csv'),
    path('upload-success/', TemplateView.as_view(template_name='upload_success.html'), name='upload_success'),
    path('search/', RepresentedVariableSearchView.as_view(), name='representedvariable_search'),
]

