# -- STDLIB
import time

# -- DJANGO
from django.core.management.base import BaseCommand

# -- BASEDEQUESTIONS
from app.models import (
    BindingConcept,
    BindingSurveyRepresentedVariable,
    Category,
    Collection,
    Concept,
    ConceptualVariable,
    Distributor,
    RepresentedVariable,
    Subcollection,
    Survey,
)


class Command(BaseCommand):
    help = "Supprime toutes les données de la base de données dans un ordre spécifique"

    def handle(self, *args, **kwargs):
        start_time = time.time()  # Début de la mesure du temps global
        print("Démarrage de la suppression des données...")

        # Supprimer les données dans l'ordre correct pour éviter les problèmes de dépendances
        models_to_delete = [
            (BindingConcept, "BindingConcept"),
            (BindingSurveyRepresentedVariable, "BindingSurveyRepresentedVariable"),
            (Category, "Category"),
            (Concept, "Concept"),
            (RepresentedVariable, "RepresentedVariable"),
            (ConceptualVariable, "ConceptualVariable"),
            (Survey, "Survey"),
            (Subcollection, "Subcollection"),
            (Collection, "Collection"),
            (Distributor, "Distributor"),
        ]

        for model, name in models_to_delete:
            model_start_time = (
                time.time()
            )  # Début de la mesure du temps pour chaque modèle
            model.objects.all().delete()
            model_end_time = time.time()  # Fin de la mesure du temps pour chaque modèle

            print(
                f"{name} supprimé avec succès en {model_end_time - model_start_time:.4f} secondes."
            )
            self.stdout.write(self.style.SUCCESS(f"Deleted {name}"))

        end_time = time.time()  # Fin de la mesure du temps global
        print(
            f"Toutes les données ont été supprimées avec succès en {end_time - start_time:.4f} secondes."
        )
        self.stdout.write(self.style.SUCCESS("All data cleared successfully!"))
