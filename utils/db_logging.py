import logging
import time

from django.db import connection

logger = logging.getLogger("performance")

class DBQueryLogger:
    def __init__(self):
        self.original_execute = connection.cursor().execute

    def log_query(self, sql, params, many=False):
        start_time = time.time()

        result = self.original_execute(sql, params, many)

        elapsed_time = time.time() - start_time

        logger.debug(f"DB Query: {sql} | Time: {elapsed_time:.4f}s")

        return result

    def enable(self):
        connection.cursor().execute = self.log_query

    def disable(self):
        connection.cursor().execute = self.original_execute
