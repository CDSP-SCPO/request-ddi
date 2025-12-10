import os
import warnings
from unittest.mock import patch

import requests

# Filtrer les warnings Python (Whitenoise)
warnings.simplefilter("ignore", UserWarning)

# Patch global du logger des vues bruyantes
patch("request_ddi.views.search_views.logger").start()


def is_elasticsearch_available():
    es_url = os.getenv("ELASTICSEARCH_URL")
    if not es_url:
        return False

    try:
        response = requests.options(es_url, timeout=5)
        return response.ok
    except Exception:
        return False
