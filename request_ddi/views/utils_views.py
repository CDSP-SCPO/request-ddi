# -- STDLIB
import re

# -- DJANGO

VALID_SEARCH_LOCATIONS = frozenset({"questions", "categories", "variable_name", "internal_label"})
ALL_SEARCH_LOCATIONS = list(VALID_SEARCH_LOCATIONS)


def remove_html_tags(text):
    """Supprime toutes les balises HTML d'une chaîne de caractères."""
    return re.sub(r"<[^>]+>", "", text)


def validate_search_locations(search_locations):
    valid = [loc for loc in search_locations if loc in VALID_SEARCH_LOCATIONS]
    return valid or ALL_SEARCH_LOCATIONS
