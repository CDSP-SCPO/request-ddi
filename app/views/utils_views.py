# -- STDLIB
import re

# -- THIRDPARTY
import requests

# -- DJANGO
from django.conf import settings


def remove_html_tags(text):
    """Supprime toutes les balises HTML d'une chaîne de caractères."""
    return re.sub(r"<[^>]+>", "", text)


def admin_required(user):
    return user.is_authenticated and user.is_staff


def check_file_access(file_url):
    """
    Fonction qui essaie de faire une requête HTTP GET pour vérifier si l'URL du fichier est accessible.
    Retourne True si le fichier est accessible, sinon False.
    """

    # Construire l'URL complète (en prenant en compte la configuration du domaine et du path)
    # Ici, on assume que l'URL du fichier est accessible via un domaine public
    full_url = f"http://{settings.ALLOWED_HOSTS[0]}{file_url}"

    try:
        response = requests.get(full_url)
        # Si le code de réponse est 200, cela signifie que le fichier est accessible
        return response.status_code == 200
    except requests.exceptions.RequestException:
        # Si une exception se produit, on considère que le fichier n'est pas accessible
        return False
