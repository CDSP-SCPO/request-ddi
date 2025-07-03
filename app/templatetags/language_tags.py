from django import template
from django.utils import translation
from django.conf import settings

register = template.Library()

@register.simple_tag
def get_current_language():
    return translation.get_language()

@register.simple_tag
def get_available_languages():
    return settings.LANGUAGES
