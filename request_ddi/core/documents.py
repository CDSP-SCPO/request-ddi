# -- STDLIB
import logging
import time

# -- THIRDPARTY
from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry
from elasticsearch.exceptions import NotFoundError
from elasticsearch.helpers import bulk

from request_ddi.views.utils_views import (
    validate_search_locations,
)

# -- REQUEST_DDI (LOCAL)
from .models import BindingSurveyRepresentedVariable

logger = logging.getLogger(__name__)


@registry.register_document
class BindingSurveyDocument(Document):
    survey = fields.ObjectField(
        properties={
            "id": fields.IntegerField(),
            "name": fields.TextField(),
            "external_ref": fields.TextField(),
            "start_date": fields.DateField(),
            "subcollection": fields.ObjectField(
                properties={
                    "id": fields.IntegerField(),
                    "collection_id": fields.IntegerField(),
                }
            ),
        }
    )
    variable = fields.ObjectField(
        properties={
            "id": fields.IntegerField(),
            "question_text": fields.TextField(analyzer="combined_analyzer"),
            "internal_label": fields.TextField(analyzer="combined_analyzer"),
            "categories": fields.NestedField(
                properties={
                    "code": fields.TextField(),
                    "category_label": fields.TextField(analyzer="combined_analyzer"),
                }
            ),
        }
    )

    class Index:
        name = "binding_survey_variables"
        settings = {  # noqa: RUF012
            "index": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "analysis": {
                    "char_filter": {
                        "elided_articles": {
                            "type": "pattern_replace",
                            "pattern": r"(?i)\b(l|d|j|qu|n|c|m|s|t)'",
                            "replacement": "",
                        }
                    },
                    "filter": {
                        "asciifolding_filter": {
                            "type": "asciifolding",
                            "preserve_original": False,
                        },
                        "french_stop": {
                            "type": "stop",
                            "stopwords": [
                                "_french_",
                                "a",
                            ],
                        },
                    },
                    "analyzer": {
                        "combined_analyzer": {
                            "type": "custom",
                            "tokenizer": "standard",
                            "char_filter": ["elided_articles"],
                            "filter": [
                                "lowercase",
                                "asciifolding_filter",
                                "french_stop",
                            ],
                        }
                    },
                },
            }
        }

    class Django:
        model = BindingSurveyRepresentedVariable
        fields = [  # noqa: RUF012
            "variable_name",
            "notes",
            "universe",
        ]

    def update(self, instances, batch_size=1000, **kwargs):
        """Met à jour des documents dans l'index Elasticsearch."""
        # Uniformiser : transformer en liste si c'est un seul objet
        if isinstance(instances, BindingSurveyRepresentedVariable):
            instances = [instances]
        elif not isinstance(instances, list):
            instances = list(instances)

        # Update ES index in batches of batch_size
        for i in range(0, len(instances), batch_size):
            try:
                actions = [
                    {
                        "_op_type": "index",
                        "_index": self._index._name,
                        "_id": instance.pk,
                        "_source": self.serialize(instance),
                    }
                    for instance in instances[i : i + batch_size]
                ]
                bulk(self._get_connection(), actions, refresh=True)
            except Exception as ex:
                logger.exception("Erreur lors de l'update: %s", ex)
                raise ex  # Need to raise exception here so that it will be caught in the caller

    def delete(self, instance):
        """Supprime un document de l'index Elasticsearch."""
        try:
            # Vérifier si le document existe dans Elasticsearch avant de tenter de le supprimer
            self._get_connection().get(index=self._index._name, id=instance.pk)
            self._get_connection().delete(index=self._index._name, id=instance.pk)

        except Exception as ex:
            logger.exception(
                "Erreur lors de la suppression du document avec l'ID %s: %s", instance.pk, ex
            )
            raise ex

    def serialize(self, instance):
        """Prépare les données du document pour Elasticsearch."""
        categories = [
            {"code": category.code, "category_label": category.category_label}
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
                    "id": instance.survey.subcollection.id
                    if instance.survey.subcollection
                    else None,
                    "collection_id": instance.survey.subcollection.collection.id
                    if instance.survey.subcollection and instance.survey.subcollection.collection
                    else None,
                },
            },
            "variable": {
                "id": instance.variable.id,
                "question_text": instance.variable.question_text,
                "internal_label": instance.variable.internal_label,
                "categories": categories,
            },
        }

    def update_index(self):
        """Met à jour l'index Elasticsearch avec les documents non indexés."""
        start_time = time.time()
        logger.info("Démarrage de l'update de l'index pour les documents non indexés...")

        try:
            qs = self.get_queryset().filter(is_indexed=False)  # Obtenir les documents non indexés
            actions = [
                {
                    "_op_type": "index",
                    "_index": self._index._name,
                    "_id": instance.pk,
                    "_source": self.serialize(instance),
                }
                for instance in qs
            ]

            bulk(self._get_connection(), actions, refresh=True)

            # Mettre à jour le champ is_indexed pour les documents indexés
            qs.update(is_indexed=True)

        except Exception as ex:
            logger.exception("An unexpected error occurred: %s", ex)

        end_time = time.time()
        logger.info("Temps total de l'update de l'index: %.4f secondes.", end_time - start_time)

    def clean_orphaned_documents(self):
        """Supprime les documents Elasticsearch qui ne sont plus présents en base de données."""
        logger.info("🔍 Recherche des documents orphelins dans Elasticsearch...")

        # Obtenir tous les IDs en base
        db_ids = set(BindingSurveyRepresentedVariable.objects.values_list("id", flat=True))

        # Obtenir tous les IDs dans l'index
        es = self._get_connection()
        index_name = self._index._name

        try:
            es_ids = set()
            scroll = es.search(
                index=index_name,
                scroll="2m",
                size=1000,
                body={"query": {"match_all": {}}},
            )
            scroll_id = scroll["_scroll_id"]
            hits = scroll["hits"]["hits"]

            while hits:
                for hit in hits:
                    es_ids.add(int(hit["_id"]))
                scroll = es.scroll(scroll_id=scroll_id, scroll="2m")
                scroll_id = scroll["_scroll_id"]
                hits = scroll["hits"]["hits"]

            # Identifier les documents à supprimer
            orphan_ids = es_ids - db_ids
            logger.info("🧹 %d documents orphelins trouvés à supprimer.", len(orphan_ids))

            for orphan_id in orphan_ids:
                try:
                    es.delete(index=index_name, id=orphan_id)
                    logger.info("❌ Document supprimé : ID %s", orphan_id)
                except NotFoundError:
                    logger.warning("⚠️ Document déjà supprimé : ID %s", orphan_id)

        except Exception as e:
            logger.exception(
                "Erreur lors du nettoyage de l'index pour le document ID %s : %s",
                orphan_id,
                e,
            )

    @classmethod
    def search_with_filters(
        cls,
        *,
        query="",
        search_locations=None,
        survey_ids=None,
        collection_ids=None,
        sub_collection_ids=None,
        years=None,
        selected_ids=None,
        aggregations=False,
    ):
        search = cls.search()
        search_locations = validate_search_locations(search_locations or [])

        # Always return results in descending order of the survey. Newer survey results
        # appear at the top of the search!
        # Important to use _score as the first sorting variable as we need to ALWAYS
        # present results by the relevance of the search term. If the score is same
        # for all results (in case of empty search term), we use survey.start_date as
        # tiebreaker to sort results based on survey date.
        # See: https://gitlab.sciences-po.fr/cdspit/request/request-ddi/-/merge_requests/477#note_24351
        search = search.sort("_score", {"survey.start_date": {"order": "desc"}})

        if query:
            queries = cls._build_search_location_queries(query, search_locations)
            if queries:
                search = search.query("bool", should=queries, minimum_should_match=1)

        if selected_ids:
            search = search.filter("ids", values=selected_ids)

        if survey_ids:
            search = search.filter("terms", **{"survey.id": survey_ids})

        if sub_collection_ids:
            search = search.filter("terms", **{"survey.subcollection.id": sub_collection_ids})

        if collection_ids:
            search = search.filter(
                "terms", **{"survey.subcollection.collection_id": collection_ids}
            )

        if years:
            search = search.query(
                "bool",
                should=[
                    {
                        "range": {
                            "survey.start_date": {"gte": f"{year}-01-01", "lt": f"{year + 1}-01-01"}
                        }
                    }
                    for year in years
                ],
                minimum_should_match=1,
            )
        if aggregations:
            search = cls.add_filter_aggregations(
                search,
                query=query,
                search_locations=search_locations,
                survey_ids=survey_ids,
                collection_ids=collection_ids,
                sub_collection_ids=sub_collection_ids,
                years=years,
            )

        return search

    @staticmethod
    def _build_search_location_queries(query: str, search_locations: list[str]) -> list:
        queries = []
        terms = query.split()

        for search_location in search_locations:
            if search_location == "questions":
                queries += [
                    {
                        "match_phrase_prefix": {
                            "variable.question_text": {"query": query, "boost": 10}
                        }
                    },
                    {
                        "match": {
                            "variable.question_text": {
                                "query": query,
                                "operator": "and",
                                "boost": 5,
                            }
                        }
                    },
                    *[
                        {
                            "match": {
                                "variable.question_text": {
                                    "query": term,
                                    "operator": "or",
                                    "boost": 1,
                                }
                            }
                        }
                        for term in terms
                    ],
                ]
            elif search_location == "categories":
                queries.append(
                    {
                        "nested": {
                            "path": "variable.categories",
                            "query": {
                                "bool": {
                                    "should": [
                                        {
                                            "match_phrase_prefix": {
                                                "variable.categories.category_label": {
                                                    "query": query,
                                                    "boost": 10,
                                                }
                                            }
                                        },
                                        {
                                            "match": {
                                                "variable.categories.category_label": {
                                                    "query": query,
                                                    "operator": "and",
                                                    "boost": 5,
                                                }
                                            }
                                        },
                                        *[
                                            {
                                                "match": {
                                                    "variable.categories.category_label": {
                                                        "query": term,
                                                        "operator": "or",
                                                        "boost": 1,
                                                    }
                                                }
                                            }
                                            for term in terms
                                        ],
                                    ],
                                    "minimum_should_match": 1,
                                }
                            },
                        }
                    }
                )
            elif search_location == "variable_name":
                queries += [
                    {"match_phrase_prefix": {"variable_name": {"query": query, "boost": 10}}},
                    *[
                        {"match": {"variable_name": {"query": term, "operator": "or", "boost": 5}}}
                        for term in terms
                    ],
                ]
            elif search_location == "internal_label":
                queries += [
                    {
                        "match_phrase_prefix": {
                            "variable.internal_label": {"query": query, "boost": 10}
                        }
                    },
                    {
                        "match": {
                            "variable.internal_label": {
                                "query": query,
                                "operator": "and",
                                "boost": 5,
                            }
                        }
                    },
                    *[
                        {
                            "match": {
                                "variable.internal_label": {
                                    "query": term,
                                    "operator": "or",
                                    "boost": 1,
                                }
                            }
                        }
                        for term in terms
                    ],
                ]

        return queries

    @classmethod
    def _build_facet_filter(
        cls,
        *,
        query="",
        search_locations=None,
        survey_ids=None,
        collection_ids=None,
        sub_collection_ids=None,
        years=None,
        exclude=None,
    ):
        exclude = set(exclude or [])
        filters = []

        if survey_ids and "survey" not in exclude:
            filters.append({"terms": {"survey.id": survey_ids}})

        if sub_collection_ids and "sub_collection" not in exclude:
            filters.append({"terms": {"survey.subcollection.id": sub_collection_ids}})

        if collection_ids and "collection" not in exclude:
            filters.append({"terms": {"survey.subcollection.collection_id": collection_ids}})

        if years and "years" not in exclude:
            filters.append(
                {
                    "bool": {
                        "should": [
                            {
                                "range": {
                                    "survey.start_date": {
                                        "gte": f"{year}-01-01",
                                        "lt": f"{year + 1}-01-01",
                                    }
                                }
                            }
                            for year in years
                        ],
                        "minimum_should_match": 1,
                    }
                }
            )

        must = []

        if query:
            queries = cls._build_search_location_queries(
                query,
                validate_search_locations(search_locations or []),
            )

            if queries:
                must.append(
                    {
                        "bool": {
                            "should": queries,
                            "minimum_should_match": 1,
                        }
                    }
                )

        bool_query = {}

        if must:
            bool_query["must"] = must

        if filters:
            bool_query["filter"] = filters

        return {"bool": bool_query} if bool_query else {"match_all": {}}

    @classmethod
    def add_filter_aggregations(
        cls,
        search,
        *,
        query="",
        search_locations=None,
        survey_ids=None,
        collection_ids=None,
        sub_collection_ids=None,
        years=None,
    ):
        facet_root = search.aggs.bucket("facets", "global")

        facet_definitions = {
            "collections": {
                "exclude": {
                    "collection",
                    "sub_collection",
                    "survey",
                    "years",
                },
                "aggregation": (
                    "terms",
                    {
                        "field": "survey.subcollection.collection_id",
                        "size": 10000,
                    },
                ),
            },
            "subcollections": {
                "exclude": {
                    "sub_collection",
                    "survey",
                    "years",
                },
                "aggregation": (
                    "terms",
                    {
                        "field": "survey.subcollection.id",
                        "size": 10000,
                    },
                ),
            },
            "surveys": {
                "exclude": {
                    "survey",
                    "years",
                },
                "aggregation": (
                    "terms",
                    {
                        "field": "survey.id",
                        "size": 10000,
                    },
                ),
            },
            "years": {
                "exclude": {
                    "years",
                },
                "aggregation": (
                    "date_histogram",
                    {
                        "field": "survey.start_date",
                        "calendar_interval": "year",
                        "format": "yyyy",
                        "min_doc_count": 1,
                    },
                ),
            },
        }

        for facet_name, definition in facet_definitions.items():
            facet_filter = cls._build_facet_filter(
                query=query,
                search_locations=search_locations,
                survey_ids=survey_ids,
                collection_ids=collection_ids,
                sub_collection_ids=sub_collection_ids,
                years=years,
                exclude=definition["exclude"],
            )

            scoped_facet = facet_root.bucket(
                f"{facet_name}_scope",
                "filter",
                facet_filter,
            )

            aggregation_type, aggregation_params = definition["aggregation"]

            scoped_facet.bucket(
                facet_name,
                aggregation_type,
                **aggregation_params,
            )

        if query:
            for location in [
                "questions",
                "categories",
                "variable_name",
                "internal_label",
            ]:
                facet_root.bucket(
                    location,
                    "filter",
                    cls._build_facet_filter(
                        query=query,
                        search_locations=[location],
                        survey_ids=survey_ids,
                        collection_ids=collection_ids,
                        sub_collection_ids=sub_collection_ids,
                        years=years,
                    ),
                )

        return search
