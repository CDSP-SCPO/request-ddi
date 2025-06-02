# -- STDLIB
import time

# -- THIRDPARTY
from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError
from elasticsearch.helpers import bulk

# -- BASEDEQUESTIONS (LOCAL)
from .models import BindingSurveyRepresentedVariable


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
        # Uniformiser : transformer en liste si c'est un seul objet
        if isinstance(instances, BindingSurveyRepresentedVariable):
            instances = [instances]
        elif not isinstance(instances, list):
            instances = list(instances)


        actions = [{
            '_op_type': 'index',
            '_index': self._index._name,
            '_id': instance.pk,
            '_source': self.serialize(instance)
        } for instance in instances]

        bulk(self._get_connection(), actions, refresh=True)

    def delete(self, instance):
        """Supprime un document de l'index Elasticsearch."""
        try:
            # Vérifier si le document existe dans Elasticsearch avant de tenter de le supprimer
            self._get_connection().get(index=self._index._name, id=instance.pk)
            self._get_connection().delete(index=self._index._name, id=instance.pk)

        except Exception as ex:
            print(f"Erreur lors de la suppression du document avec l'ID {instance.pk}: {ex}")

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

            bulk(self._get_connection(), actions, refresh=True)

            # Mettre à jour le champ is_indexed pour les documents indexés
            qs.update(is_indexed=True)

        except Exception as ex:
            print(f"An unexpected error occurred: {ex}")

        end_time = time.time()
        print(f"Temps total de l'update de l'index: {end_time - start_time:.4f} secondes.")

    def clean_orphaned_documents(self):
            """Supprime les documents Elasticsearch qui ne sont plus présents en base de données."""
            print("🔍 Recherche des documents orphelins dans Elasticsearch...")

            # Obtenir tous les IDs en base
            db_ids = set(BindingSurveyRepresentedVariable.objects.values_list('id', flat=True))

            # Obtenir tous les IDs dans l'index
            es = self._get_connection()
            index_name = self._index._name

            try:
                es_ids = set()
                scroll = es.search(index=index_name, scroll='2m', size=1000, body={"query": {"match_all": {}}})
                scroll_id = scroll['_scroll_id']
                hits = scroll['hits']['hits']

                while hits:
                    for hit in hits:
                        es_ids.add(int(hit['_id']))
                    scroll = es.scroll(scroll_id=scroll_id, scroll='2m')
                    scroll_id = scroll['_scroll_id']
                    hits = scroll['hits']['hits']

                # Identifier les documents à supprimer
                orphan_ids = es_ids - db_ids
                print(f"🧹 {len(orphan_ids)} documents orphelins trouvés à supprimer.")

                for orphan_id in orphan_ids:
                    try:
                        es.delete(index=index_name, id=orphan_id)
                        print(f"❌ Document supprimé : ID {orphan_id}")
                    except NotFoundError:
                        print(f"⚠️ Document déjà supprimé : ID {orphan_id}")

            except Exception as e:
                print(f"Erreur lors du nettoyage de l'index : {e}")

