# -- THIRDPARTY
from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry
from elasticsearch.helpers import BulkIndexError, bulk

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
        'subcollection': fields.ObjectField(properties={
            'id': fields.IntegerField(),
            'collection_id': fields.IntegerField()
        })
    })
    variable = fields.ObjectField(properties={
        'question_text': fields.TextField(analyzer='custom_analyzer'),
        'internal_label': fields.TextField(),
        'categories': fields.NestedField(properties={
            'code': fields.TextField(),
            'category_label': fields.TextField(analyzer='custom_analyzer'),
        }),
    })

    class Index:
        name = 'binding_survey_variables'  # Nom de l'index dans Elasticsearch
        settings = {
            'number_of_shards': 1,
            'number_of_replicas': 0,
            'analysis': {  # Ajoute une configuration d'analyse personnalisée
                'filter': {
                    'asciifolding_filter': {
                        'type': 'asciifolding',
                        'preserve_original': False  # Ignore les accents
                    }
                },
                'analyzer': {
                    'custom_analyzer': {  # Définir un analyseur personnalisé
                        'type': 'custom',
                        'tokenizer': 'standard',
                        'filter': [
                            'lowercase',  # Convertir en minuscules
                            'asciifolding_filter'  # Supprimer les accents
                        ]
                    }
                }
            }
        }


    class Django:
        model = BindingSurveyRepresentedVariable  # Le modèle Django associé
        fields = [
            'variable_name',  # Nom de la variable
            'notes',          # Notes éventuelles
            'universe',       # Univers
        ]

    def update_index(self):
        """Met à jour l'index Elasticsearch avec gestion des erreurs."""
        try:
            qs = self.get_queryset()  # Obtenir le queryset à indexer
            actions = [
                {
                    '_op_type': 'index',  # Type de l'opération (indexation)
                    '_index': self._index._name,  # Nom de l'index
                    '_id': instance.pk,  # Identifiant du document
                    '_source': self.serialize(instance)  # Prépare les données
                }
                for instance in qs
            ]
            bulk(self._get_connection(), actions, refresh=True)  # Opération en bulk
            print("Indexation terminée avec succès.")
        except BulkIndexError as e:
            # Afficher les erreurs d'indexation détaillées
            print(f"BulkIndexError occurred with {len(e.errors)} errors.")
            for error in e.errors:
                print("Erreur d'indexation :", error)
        except Exception as ex:
            # Gérer d'autres erreurs éventuelles
            print(f"An unexpected error occurred: {ex}")
    def get_queryset(self):
        """Retourne le queryset pour les instances à indexer."""
        return super(BindingSurveyDocument, self).get_queryset().select_related('survey', 'variable').prefetch_related('variable__categories')
    def get_indexing_queryset(self):
        """Retourne un générateur (iterator) pour l'indexation avec un chunk_size."""
        return self.get_queryset().iterator(chunk_size=1000)

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
                "subcollection": {
                    "collection_id": instance.survey.subcollection.collection.id if instance.survey.subcollection and instance.survey.subcollection.collection else None
                }
            },
            "variable": {
                "question_text": instance.variable.question_text,
                "internal_label": instance.variable.internal_label,
                "categories": categories
            }
        }



# from django_elasticsearch_dsl import Document, fields
# from django_elasticsearch_dsl.registries import registry
# from .models import RepresentedVariable, Survey, ConceptualVariable, BindingSurveyRepresentedVariable
# from elasticsearch.helpers import BulkIndexError, bulk

# @registry.register_document
# class RepresentedVariableDocument(Document):
#     conceptual_var = fields.ObjectField(properties={
#         'internal_label': fields.TextField(),
#     })
#     categories = fields.ObjectField(properties={
#         'code': fields.TextField(),
#         'category_label': fields.TextField(),
#     })

#     suggest = fields.CompletionField()

#     class Index:
#         name = 'represented_variables'  # Nom de l'index dans Elasticsearch
#         settings = {
#             'number_of_shards': 1,
#             'number_of_replicas': 0,
#         }

#     class Django:
#         model = RepresentedVariable  # Le modèle Django associé
#         fields = [
#             'question_text',
#             'internal_label',
#         ]

#     def prepare_suggest(self, instance):
#         """Prépare les données pour le champ d'autocomplétion."""
#         # Exclure les valeurs None de la suggestion
#         suggest_input = [text for text in [instance.question_text, instance.internal_label] if text]
        
#         if suggest_input:  # Ajouter une vérification si il y a au moins une valeur valide
#             return {
#                 "input": suggest_input,
#             }
#         else:
#             return None 

#     def get_queryset(self):
#         """Retourne le queryset pour les instances à indexer."""
#         return super(RepresentedVariableDocument, self).get_queryset().select_related('conceptual_var')

#     def get_instances_from_related(self, related_instance):
#         """Retourne les instances liées à l'objet lié."""
#         if isinstance(related_instance, Survey):
#             return related_instance.representedvariable_set.all()
#         elif isinstance(related_instance, ConceptualVariable):
#             return related_instance.representedvariable_set.all()

#     def update_index(self):
#         """Met à jour l'index Elasticsearch avec gestion des erreurs."""
#         try:
#             qs = self.get_queryset()  # Obtenir le queryset à indexer
#             actions = [
#                 {
#                     '_op_type': 'index',  # Type de l'opération (indexation)
#                     '_index': self._index._name,  # Nom de l'index
#                     '_id': instance.pk,  # Identifiant du document
#                     '_source': self.serialize(instance)  # Prépare les données
#                 }
#                 for instance in qs
#             ]
#             bulk(self._get_connection(), actions, refresh=True)  # Opération en bulk
#             print("Indexation terminée avec succès.")
#         except BulkIndexError as e:
#             # Afficher les erreurs d'indexation détaillées
#             print(f"BulkIndexError occurred with {len(e.errors)} errors.")
#             for error in e.errors:
#                 print("Erreur d'indexation :", error)
#         except Exception as ex:
#             # Gérer d'autres erreurs éventuelles
#             print(f"An unexpected error occurred: {ex}")
#     def serialize(self, instance):
#         """Prépare les données du document pour Elasticsearch."""
#         suggest_input = [text for text in [instance.question_text, instance.internal_label] if text]
#         surveys = BindingSurveyRepresentedVariable.objects.filter(variable=instance)
#         survey_ids = [binding.survey.id for binding in surveys]

#         return {
#             "question_text": instance.question_text,
#             "internal_label": instance.internal_label,
#             "conceptual_var": {
#                 "internal_label": instance.conceptual_var.internal_label if instance.conceptual_var else None
#             },
#             "categories": [
#                 {
#                     "code": category.code,
#                     "category_label": category.category_label
#                 }
#                 for category in instance.categories.all()
#             ],
#             "survey_ids": survey_ids,  
#             "suggest": {
#                 "input": suggest_input,
#             }
#         }
