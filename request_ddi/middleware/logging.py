import logging
import time

logger = logging.getLogger("performance")


class ResponseTimeLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        response = self.get_response(request)
        total_time = time.time() - start_time

        logger.debug(
            f"URL: {request.path} | Total time: {total_time:.4f}s | Method: {request.method}"
        )

        return response
