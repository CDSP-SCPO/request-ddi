"""
URL configuration for basedequestions project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# -- DJANGO
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
import debug_toolbar

# -- BASEDEQUESTIONS
from app.views import ExportQuestionsCSVView, autocomplete

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('app.urls')),
    path('autocomplete/', autocomplete, name='autocomplete'),
    path('export/questions/', ExportQuestionsCSVView.as_view(), name='export_questions_csv'),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)