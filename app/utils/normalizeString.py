import unicodedata
import re

def normalize_string_for_database(value):
    if not isinstance(value, str):
        return value

    # Normalisation Unicode (NFKC)
    text = unicodedata.normalize('NFKC', value)

    # Remplacement des espaces insécables par des espaces standards
    text = re.sub(r"[\u00A0\u202F\u2007\u2060\u2027\u00B7]", " ", text)

    # Remplacement des guillemets typographiques par des guillemets standards
    text = text.replace("«", '"').replace("»", '"')
    text = text.replace("“", '"').replace("”", '"')

    # Ajout d'un espace avant les ponctuations suivantes : `? ;`
    text = re.sub(r"(?<!\s)([?;])", r" \1", text)

    # Ajout d'un espace après les guillemets
    text = re.sub(r'(?<!\s)(["])', r' \1', text)

    text = re.sub(r'(["])(?=\S)', r'\1 ', text)

    # Uniformisation des apostrophes et tirets
    text = text.replace("’", "'").replace("–", "-")

    # Remplacement des points de suspension et normalisation des espaces
    text = text.replace("…", "...")
    text = re.sub(r"\.{3,}", "...", text)

    # Suppression des espaces en trop (double espaces, espaces en début et fin)
    text = " ".join(text.split())

    return text

def normalize_string_for_comparison(value):
    if not isinstance(value, str):
        return value 

    # Normalisation Unicode pour décomposer les accents
    text = unicodedata.normalize('NFD', value)

    # Suppression des accents (en gardant uniquement les caractères ASCII)
    text = "".join(char for char in text if unicodedata.category(char) != 'Mn')

    text = text.lower()

    return text