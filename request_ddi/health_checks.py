from django.conf import settings
from elasticsearch import Elasticsearch
from health_check.backends import BaseHealthCheckBackend
from health_check.exceptions import ServiceUnavailable


class ElasticsearchHealthCheck(BaseHealthCheckBackend):
    """
    Checks if the Elasticsearch cluster is reachable from Django.
    """

    def __init__(self):
        super().__init__()
        self.es = Elasticsearch(**settings.ELASTICSEARCH_DSL["default"])

    def check_status(self):
        if not self.es.ping():
            message = "Elasticsearch cluster not responding"
            raise ServiceUnavailable(message)

    def identifier(self):
        return "ElasticsearchHealthCheck"
