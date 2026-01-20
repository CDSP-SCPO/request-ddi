# -- STDLIB
import logging
import time

# -- DJANGO
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models.signals import post_delete, post_save

# -- ELASTICSEARCH
from elasticsearch import Elasticsearch

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
from request_ddi.core.signals import delete_index, update_index

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Supprime toutes les données de la base de données et réinitialise l'index Elasticsearch"

    def handle(self, *args, **kwargs):
        start_time = time.time()
        logger.info("Démarrage de la suppression des données...")

        # --- Désactivation des signaux ---
        post_save.disconnect(update_index, sender=BindingSurveyRepresentedVariable)
        post_delete.disconnect(delete_index, sender=BindingSurveyRepresentedVariable)

        # --- Suppression des données ---
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
            model_start_time = time.time()
            deleted_count, _ = model.objects.all().delete()
            model_end_time = time.time()
            duration = model_end_time - model_start_time
            logger.info("%s supprimé avec succès en %.4f secondes.", name, duration)
            self.stdout.write(self.style.SUCCESS(f"Deleted {name} ({deleted_count} objets)"))

        # --- Réactivation des signaux ---
        post_save.connect(update_index, sender=BindingSurveyRepresentedVariable)
        post_delete.connect(delete_index, sender=BindingSurveyRepresentedVariable)

        es_url = settings.ELASTICSEARCH_URL
        es_user = settings.ELASTICSEARCH_ADMIN_USER
        es_password = settings.ELASTICSEARCH_ADMIN_PASSWORD

        es = Elasticsearch(es_url, basic_auth=(es_user, es_password))
        index_to_clear = "binding_survey_variables"

        try:
            response = es.delete_by_query(
                index=index_to_clear,
                body={"query": {"match_all": {}}},
                conflicts="proceed"
            )
            deleted_docs = response.get("deleted", 0)
            logger.info("Index Elasticsearch '%s' réinitialisé, %d documents supprimés.", index_to_clear, deleted_docs)
            self.stdout.write(self.style.SUCCESS(f"Elasticsearch index '{index_to_clear}' cleared ({deleted_docs} documents)"))
        except Exception as e:
            logger.error("Erreur lors de la suppression de l'index Elasticsearch : %s", str(e))
            self.stderr.write(self.style.ERROR(f"Failed to clear Elasticsearch index '{index_to_clear}'"))

        end_time = time.time()
        total_duration = end_time - start_time
        logger.info(
            "Toutes les données et l'index Elasticsearch ont été réinitialisés en %.4f secondes.", total_duration
        )
        self.stdout.write(self.style.SUCCESS("All data and Elasticsearch index cleared successfully!"))
