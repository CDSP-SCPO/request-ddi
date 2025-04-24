import time
from elasticsearch.exceptions import NotFoundError

# -- DJANGO
from django.utils import timezone

# -- THIRDPARTY
from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

# -- BASEDEQUESTIONS (LOCAL)
from .models import (
    BindingSurveyRepresentedVariable, RepresentedVariable, Survey,
)


@registry.register_document
class BindingSurveyDocument(Document):
    survey = fields.ObjectField(properties={
        'id': fields.IntegerField(),
        'name': fields.TextField(),
        'external_ref': fields.TextField(),
        "start_date": fields.DateField(),
        'subcollection': fields.ObjectField(properties={
            'id': fields.IntegerField(),
            'collection_id': fields.IntegerField()
        })
    })
    variable = fields.ObjectField(properties={
        'question_text': fields.TextField(analyzer='combined_analyzer'),
        'internal_label': fields.TextField(analyzer='combined_analyzer'),
        'categories': fields.NestedField(properties={
            'code': fields.TextField(),
            'category_label': fields.TextField(analyzer='combined_analyzer'),
        }),
    })

    class Index:
        name = 'binding_survey_variables'
        settings = {
            'index': {
                'number_of_shards': 1,
                'number_of_replicas': 0,
                'analysis': {
                    'char_filter': {
                        'elided_articles': {
                            'type': 'pattern_replace',
                            'pattern': r"(?i)\b(l|d|j|qu|n|c|m|s|t)'",
                            'replacement': ""
                        }
                    },
                    'filter': {
                        'asciifolding_filter': {
                            'type': 'asciifolding',
                            'preserve_original': False
                        },
                        'french_stop': {
                            'type': 'stop',
                            'stopwords': '_french_'
                        }
                    },
                    'analyzer': {
                        'combined_analyzer': {
                            'type': 'custom',
                            'tokenizer': 'standard',
                            'char_filter': ['elided_articles'],
                            'filter': [
                                'lowercase',
                                'asciifolding_filter',
                                'french_stop'
                            ]
                        }
                    }
                }
            }
        }

    class Django:
        model = BindingSurveyRepresentedVariable
        fields = [
            'variable_name',
            'notes',
            'universe',
        ]

    def update(self, instances, **kwargs):
        """Met à jour des documents dans l'index Elasticsearch."""
        start_time = time.time()  # Début de la mesure du temps

        # Uniformiser : transformer en liste si c'est un seul objet
        if isinstance(instances, BindingSurveyRepresentedVariable):
            instances = [instances]
        elif not isinstance(instances, list):
            instances = list(instances)

        print(f"Démarrage de l'update avec {len(instances)} instance(s)...")

        actions = [{
            '_op_type': 'index',
            '_index': self._index._name,
            '_id': instance.pk,
            '_source': self.serialize(instance)
        } for instance in instances]

        bulk_start_time = time.time()
        bulk(self._get_connection(), actions, refresh=True)
        bulk_end_time = time.time()

        print(f"Opération de bulk terminée en {bulk_end_time - bulk_start_time:.4f} secondes.")
        end_time = time.time()
        print(f"Temps total pour l'update: {end_time - start_time:.4f} secondes.")

    def delete(self, instance):
        """Supprime un document de l'index Elasticsearch avec suivi du temps."""
        start_time = time.time()  # Début de la mesure du temps
        print(f"Démarrage de la suppression du document avec l'ID {instance.pk}...")

        try:
            # Vérifier si le document existe dans Elasticsearch avant de tenter de le supprimer
            check_start_time = time.time()
            self._get_connection().get(index=self._index._name, id=instance.pk)
            check_end_time = time.time()
            print(
                f"Vérification de l'existence du document ID {instance.pk} : {check_end_time - check_start_time:.4f} secondes.")

            delete_start_time = time.time()  # Temps de début pour la suppression
            self._get_connection().delete(index=self._index._name, id=instance.pk)
            delete_end_time = time.time()  # Temps de fin pour la suppression

            print(
                f"Suppression du document ID {instance.pk} réussie : {delete_end_time - delete_start_time:.4f} secondes.")

        except NotFoundError:
            print(f"Le document avec l'ID {instance.pk} n'a pas été trouvé dans l'index.")

        except Exception as ex:
            print(f"Erreur lors de la suppression du document avec l'ID {instance.pk}: {ex}")

        end_time = time.time()
        print(
            f"Temps total de l'opération de suppression pour l'ID {instance.pk}: {end_time - start_time:.4f} secondes.")

    def serialize(self, instance):
        """Prépare les données du document pour Elasticsearch."""
        categories = [
            {
                "code": category.code,
                "category_label": category.category_label
            }
            for category in instance.variable.categories.all()
        ]
        return {
            "variable_name": instance.variable_name,
            "notes": instance.notes,
            "universe": instance.universe,
            "survey": {
                "id": instance.survey.id,
                "name": instance.survey.name,
                "external_ref": instance.survey.external_ref,
                "start_date": instance.survey.start_date,
                "subcollection": {
                    "id": instance.survey.subcollection.id if instance.survey.subcollection else None,
                    "collection_id": instance.survey.subcollection.collection.id if instance.survey.subcollection and instance.survey.subcollection.collection else None
                }
            },
            "variable": {
                "question_text": instance.variable.question_text,
                "internal_label": instance.variable.internal_label,
                "categories": categories
            },
            "is_question_text_empty": not bool(instance.variable.question_text.strip())
        }

    def update_index(self):
        """Met à jour l'index Elasticsearch avec les documents non indexés."""
        start_time = time.time()
        print("Démarrage de l'update de l'index pour les documents non indexés...")

        try:
            qs = self.get_queryset().filter(is_indexed=False)  # Obtenir les documents non indexés
            actions = [
                {
                    '_op_type': 'index',
                    '_index': self._index._name,
                    '_id': instance.pk,
                    '_source': self.serialize(instance)
                }
                for instance in qs
            ]

            bulk_start_time = time.time()
            bulk(self._get_connection(), actions, refresh=True)
            bulk_end_time = time.time()
            print(f"Indexation terminée avec succès en {bulk_end_time - bulk_start_time:.4f} secondes.")

            # Mettre à jour le champ is_indexed pour les documents indexés
            qs.update(is_indexed=True)

        except Exception as ex:
            print(f"An unexpected error occurred: {ex}")

        end_time = time.time()
        print(f"Temps total de l'update de l'index: {end_time - start_time:.4f} secondes.")
