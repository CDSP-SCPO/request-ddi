# -- STDLIB
import logging

# -- THIRDPARTY
from bs4 import BeautifulSoup

from request_ddi.utils.timing import timed

logger = logging.getLogger(__name__)


@timed
def parse_codebook_xml_file(file):
    """Parse un fichier XML et retourne les données extraites ou None s'il y a une erreur."""
    try:
        file.seek(0)
        content = file.read().decode("utf-8")
        soup = BeautifulSoup(content, "xml")

        doi_tag = soup.find("IDNo", attrs={"agency": "DataCite"}) or soup.find("IDNo")
        doi = doi_tag.text.strip() if doi_tag else None

        if not doi or not doi.startswith("doi:"):
            logger.error("DOI %s invalide (doit commencer par 'doi:')", doi)
            return None

        data = {"doi": doi, "variables": []}
        for line in soup.find_all("var"):
            categories = [
                {
                    "label": cat.find("labl").text.strip() if cat.find("labl") else "",
                    "code": cat.find("catValu").text.strip() if cat.find("catValu") else "",
                    "stat": cat.find("catStat").text.strip() if cat.find("catStat") else 0,
                    "missing": bool(cat.get("missing") == "Y"),
                }
                for cat in line.find_all("catgry")
            ]

            data["variables"].append(
                {
                    "name": line["name"].strip(),
                    "label": line.find("labl").text.strip() if line.find("labl") else "",
                    "text": line.find("qstnLit").text.strip() if line.find("qstnLit") else "",
                    "categories": categories,
                    "universe": line.find("universe").text.strip() if line.find("universe") else "",
                    "notes": line.find("notes").text.strip() if line.find("notes") else "",
                }
            )

        return data
    except Exception as e:
        logger.error("Erreur lors du parsing du fichier %s: %s", file.name, str(e))
        raise e
