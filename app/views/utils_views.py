# -- STDLIB
import re

# -- DJANGO


def remove_html_tags(text):
    """Supprime toutes les balises HTML d'une chaîne de caractères."""
    return re.sub(r"<[^>]+>", "", text)


