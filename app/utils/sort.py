# -- STDLIB
import re


def alphanum_key(s):
    """Fonction pour extraire les parties numériques et non numériques."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]