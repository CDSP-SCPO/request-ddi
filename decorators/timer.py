import logging
import time
from functools import wraps

logger = logging.getLogger("performance")

def log_time(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()

        result = func(*args, **kwargs)

        elapsed_time = time.time() - start_time

        logger.debug(f"Endpoint: {func.__name__} | Time: {elapsed_time:.4f}s")

        return result
    return wrapper
