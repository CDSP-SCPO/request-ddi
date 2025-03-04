# -- DJANGO
from django.contrib import admin

# -- BASEDEQUESTIONS (LOCAL)
from .models import *

admin.site.register(Survey)
admin.site.register(ConceptualVariable)
admin.site.register(Category)
admin.site.register(RepresentedVariable)
admin.site.register(BindingSurveyRepresentedVariable)
admin.site.register(Concept)
admin.site.register(BindingConcept)
admin.site.register(Serie)
admin.site.register(Distributor)