from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry
from .models import RepresentedVariable, Survey, ConceptualVariable
from elasticsearch.helpers import BulkIndexError, bulk

@registry.register_document
class RepresentedVariableDocument(Document):
    conceptual_var = fields.ObjectField(properties={
        'internal_label': fields.TextField(),
    })
    categories = fields.ObjectField(properties={
        'code': fields.TextField(),
        'category_label': fields.TextField(),
    })

    suggest = fields.CompletionField()

    class Index:
        name = 'represented_variables'  # Nom de l'index dans Elasticsearch
        settings = {
            'number_of_shards': 1,
            'number_of_replicas': 0,
        }

    class Django:
        model = RepresentedVariable  # Le modèle Django associé
        fields = [
            'question_text',
            'internal_label',
        ]

    def prepare_suggest(self, instance):
        """Prépare les données pour le champ d'autocomplétion."""
        # Exclure les valeurs None de la suggestion
        suggest_input = [text for text in [instance.question_text, instance.internal_label] if text]
        
        if suggest_input:  # Ajouter une vérification si il y a au moins une valeur valide
            return {
                "input": suggest_input,
            }
        else:
            return None 

    def get_queryset(self):
        """Retourne le queryset pour les instances à indexer."""
        return super(RepresentedVariableDocument, self).get_queryset().select_related('conceptual_var')

    def get_instances_from_related(self, related_instance):
        """Retourne les instances liées à l'objet lié."""
        if isinstance(related_instance, Survey):
            return related_instance.representedvariable_set.all()
        elif isinstance(related_instance, ConceptualVariable):
            return related_instance.representedvariable_set.all()

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
    def serialize(self, instance):
        """Prépare les données du document pour Elasticsearch."""
        suggest_input = [text for text in [instance.question_text, instance.internal_label] if text]
        
        return {
            "question_text": instance.question_text,
            "internal_label": instance.internal_label,
            "conceptual_var": {
                "internal_label": instance.conceptual_var.internal_label if instance.conceptual_var else None
            },
            "categories": [
                {
                    "code": category.code,
                    "category_label": category.category_label
                }
                for category in instance.categories.all()
            ],
            "suggest": {
                "input": suggest_input,  # Exclure les valeurs nulles du tableau
            }
        }
