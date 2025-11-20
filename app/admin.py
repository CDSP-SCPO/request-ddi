# -- DJANGO
from django.contrib import admin

# -- BASEDEQUESTIONS (LOCAL)
from .models import (
    BindingConcept,
    BindingSurveyRepresentedVariable,
    BindingVariableCategoryStat,
    Category,
    Collection,
    Concept,
    ConceptualVariable,
    Distributor,
    RepresentedVariable,
    Subcollection,
    Survey,
)

admin.site.register(Survey)
admin.site.register(ConceptualVariable)
admin.site.register(Category)
admin.site.register(RepresentedVariable)
admin.site.register(BindingSurveyRepresentedVariable)
admin.site.register(Concept)
admin.site.register(BindingConcept)
admin.site.register(Collection)
admin.site.register(Subcollection)
admin.site.register(Distributor)
admin.site.register(BindingVariableCategoryStat)
