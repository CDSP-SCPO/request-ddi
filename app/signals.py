# -- DJANGO
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import Signal, receiver

# -- BASEDEQUESTIONS (LOCAL)
from .documents import BindingSurveyDocument
from .models import (
    BindingSurveyRepresentedVariable, Category, ConceptualVariable,
    RepresentedVariable, Survey,
)

# Définir un signal personnalisé
data_imported = Signal()

@receiver(pre_delete, sender=Survey)
def delete_related_data_on_survey_delete(sender, instance, **kwargs):
    # Récupérer toutes les liaisons (bindings) associées à l'enquête avant suppression
    bindings = BindingSurveyRepresentedVariable.objects.filter(survey=instance)
    bindings.delete()  # Supprime toutes les liaisons associées à l'enquête

    unlinked_represented_variables = RepresentedVariable.objects.filter(bindingsurveyrepresentedvariable__isnull=True)
    unlinked_represented_variables.delete()
    unlinked_conceptual_variables = ConceptualVariable.objects.filter(representedvariable__isnull=True)
    unlinked_conceptual_variables.delete()
    print("unlinked_conceptual_variables", unlinked_conceptual_variables)

    # Lister les catégories qui ne sont liées à aucune variable représentée
    categories_without_variables = Category.objects.filter(variables__isnull=True)
    print("categories_without_variables", categories_without_variables)
    categories_without_variables.delete()

@receiver(post_save, sender=BindingSurveyRepresentedVariable)
def update_index(sender, instance, **kwargs):
    BindingSurveyDocument().update(instance)

@receiver(post_delete, sender=BindingSurveyRepresentedVariable)
def delete_index(sender, instance, **kwargs):
    BindingSurveyDocument().delete(instance)

@receiver(data_imported)
def handle_data_imported(sender, instance, **kwargs):
    BindingSurveyDocument().update(instance)

def delete_represented_variable_if_unused(represented_variable):
    categories = represented_variable.categories.all()

    # Supprimer la variable représentée
    represented_variable.delete()

    # Supprimer les catégories si elles ne sont plus utilisées
    for category in categories:
        if not category.variables.exists():
            print(f"Deleting category: {category.category_label}")
            category.delete()

    # Supprimer la variable conceptuelle si elle n'est plus utilisée
    conceptual_var = represented_variable.conceptual_var
    if not RepresentedVariable.objects.filter(conceptual_var=conceptual_var).exists():
        print(f"Deleting conceptual variable: {conceptual_var.internal_label}")
        conceptual_var.delete()