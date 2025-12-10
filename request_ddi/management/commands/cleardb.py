# -- STDLIB
import logging
import time

# -- DJANGO
from django.core.management.base import BaseCommand
from django.db.models.signals import post_delete, post_save

# -- REQUEST_DDI
from request_ddi.core.models import (
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
from request_ddi.core.signals import delete_index, update_index  # Import des handlers signals

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Supprime toutes les données de la base de données dans un ordre spécifique"

    def handle(self, *args, **kwargs):
        start_time = time.time()  # Début de la mesure du temps global
        logger.info("Démarrage de la suppression des données...")

        # --- Désactivation des signaux pour BindingSurveyRepresentedVariable ---
        post_save.disconnect(update_index, sender=BindingSurveyRepresentedVariable)
        post_delete.disconnect(delete_index, sender=BindingSurveyRepresentedVariable)

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
            model_start_time = time.time()  # Début de la mesure du temps pour chaque modèle
            model.objects.all().delete()
            model_end_time = time.time()  # Fin de la mesure du temps pour chaque modèle
            duration = model_end_time - model_start_time
            logger.info("%s supprimé avec succès en %.4f secondes.", name, duration)
            self.stdout.write(self.style.SUCCESS(f"Deleted {name}"))

        # --- Réactivation des signaux ---
        post_save.connect(update_index, sender=BindingSurveyRepresentedVariable)
        post_delete.connect(delete_index, sender=BindingSurveyRepresentedVariable)

        end_time = time.time()  # Fin de la mesure du temps global
        total_duration = end_time - start_time
        logger.info(
            "Toutes les données ont été supprimées avec succès en %.4f secondes.", total_duration
        )
        self.stdout.write(self.style.SUCCESS("All data cleared successfully!"))
