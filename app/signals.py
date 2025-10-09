# -- DJANGO
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

# -- THIRDPARTY
from elasticsearch import NotFoundError

# -- BASEDEQUESTIONS (LOCAL)
from .documents import BindingSurveyDocument
from .models import (
    BindingSurveyRepresentedVariable,
    RepresentedVariable,
)


@receiver(post_save, sender=BindingSurveyRepresentedVariable)
def update_index(sender, instance, **kwargs):
    """Met à jour Elasticsearch à chaque sauvegarde d’un binding."""
    BindingSurveyDocument().update(instance)


@receiver(post_delete, sender=BindingSurveyRepresentedVariable)
def delete_index(sender, instance, **kwargs):
    """Supprime le document Elasticsearch correspondant à un binding supprimé."""
    try:
        BindingSurveyDocument().delete(instance)
    except NotFoundError:
        pass


def delete_represented_variable_if_unused(represented_variable):
    """Supprime une variable représentée et ses dépendances si elles ne sont plus utilisées."""
    categories = represented_variable.categories.all()
    represented_variable.delete()

    for category in categories:
        if not category.variables.exists():
            print(f"Deleting category: {category.category_label}")
            category.delete()

    conceptual_var = represented_variable.conceptual_var
    if not RepresentedVariable.objects.filter(conceptual_var=conceptual_var).exists():
        print(f"Deleting conceptual variable: {conceptual_var.internal_label}")
        conceptual_var.delete()
