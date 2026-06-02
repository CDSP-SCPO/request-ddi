# -- STDLIB
import functools
import logging
import time

logger = logging.getLogger("performance")


def timed(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        duration = end - start
        logger.info("⏱ La fonction '%s' a pris %.3f secondes.", func.__name__, duration)
        return result

    return wrapper
