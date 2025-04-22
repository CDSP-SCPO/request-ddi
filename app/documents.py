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
        if isinstance(instances, list):
            # Cas où on passe une liste d'instances
            actions = [
                {
                    '_op_type': 'index',
                    '_index': self._index._name,
                    '_id': instance.pk,
                    '_source': self.serialize(instance)
                }
                for instance in instances
            ]
        elif isinstance(instances, BindingSurveyRepresentedVariable):
            # Cas où on passe une seule instance
            instances = [instances]
            actions = [{
                '_op_type': 'index',
                '_index': self._index._name,
                '_id': instance.pk,
                '_source': self.serialize(instance)
            } for instance in instances]
        else:
            # Cas où on passe un générateur
            instances = list(instances)  # Convertir le générateur en liste
            actions = [{
                '_op_type': 'index',
                '_index': self._index._name,
                '_id': instance.pk,
                '_source': self.serialize(instance)
            } for instance in instances]

        bulk(self._get_connection(), actions, refresh=True)

    def delete(self, instance):
        """Supprime un document de l'index Elasticsearch."""
        self._get_connection().delete(
            index=self._index._name,
            id=instance.pk
        )

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
            bulk(self._get_connection(), actions, refresh=True)
            print("Indexation terminée avec succès.")

            # Mettre à jour le champ is_indexed pour les documents indexés
            qs.update(is_indexed=True)
        except Exception as ex:
            print(f"An unexpected error occurred: {ex}")