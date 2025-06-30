import time
import functools

def timed(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        duration = end - start
        print(f"⏱ La fonction '{func.__name__}' a pris {duration:.3f} secondes.")
        return result
    return wrapper
