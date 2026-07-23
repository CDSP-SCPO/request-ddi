import dataclasses

from django.conf import settings
from elasticsearch import Elasticsearch
from health_check.base import HealthCheck
from health_check.exceptions import ServiceUnavailable


@dataclasses.dataclass
class ElasticsearchHealthCheck(HealthCheck):
    """
    Checks if the Elasticsearch cluster is reachable from Django.
    """

    def __init__(self):
        super().__init__()
        self.es = Elasticsearch(**settings.ELASTICSEARCH_DSL["default"])

    def run(self):
        if not self.es.ping():
            message = "Elasticsearch cluster not responding"
            raise ServiceUnavailable(message)
