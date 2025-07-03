
from django.shortcuts import redirect
from django.utils.translation import activate
from django.conf import settings

def set_language_view(request):
    language = request.POST.get('language', 'fr')
    activate(language)
    request.session[settings.LANGUAGE_COOKIE_NAME] = language  # Utiliser le bon nom de cookie pour stocker la langue
    return redirect(request.META.get('HTTP_REFERER', '/'))
