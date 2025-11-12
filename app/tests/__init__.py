import warnings
from unittest.mock import patch

# Filtrer les warnings Python (Whitenoise)
warnings.simplefilter("ignore", UserWarning)

# Patch global du logger des vues bruyantes
patch("app.views.search_views.logger").start()
