# -- STDLIB
import logging

import requests

# -- THIRDPARTY
from bs4 import BeautifulSoup

from request_ddi.utils.timing import timed

from .exceptions import (
    DDICFileURLNotFoundError,
    InvalidDDICError,
    InvalidDOIError,
    MissingAttributeError,
)

logger = logging.getLogger(__name__)


@timed
def fetch_and_parse_xml(data):
    try:
        survey_url = data.get("url", "").strip()
        if not survey_url:
            msg = f"URL de l'enquête {data['doi']} introuvable"
            raise DDICFileURLNotFoundError(msg)
        content = download_xml_file(survey_url)
        ddic = parse_codebook_xml_file(content)

        # Check if DOI in XML matches with the DOI in CSV file
        if ddic["doi"] != data["doi"]:
            msg = f"Le XML téléchargé ne correspond pas à cette enquête (DOIs trouvés dans le XML : {ddic['doi']})"
            raise InvalidDDICError(msg)

        # Merge DDIC data with survey study data
        data = {**data, **ddic}
        return data
    except Exception as e:
        logger.error(
            "Erreur lors de la récupération du DDI-C de l'enquête %s: %s", data["doi"], str(e)
        )
        raise e


def parse_codebook_xml_file(content):  # noqa: PLR0915,C901
    """Parse un fichier XML et retourne les données extraites ou None s'il y a une erreur."""
    try:
        soup = BeautifulSoup(content, "xml")

        doi_tag = soup.find("IDNo", attrs={"agency": "DataCite"}) or soup.find("IDNo")
        doi = doi_tag.text.strip() if doi_tag else None

        if not doi or not doi.startswith("doi:"):
            msg = f"DOI {doi} invalide (doit commencer par 'doi:')"
            raise InvalidDOIError(msg)

        # Intialise data
        data = {"doi": doi, "variables": []}

        # Get title
        title = soup.find("titl")
        data["title"] = title.text.strip() if title else ""
        if not data["title"]:
            msg = f"L'attribut titl n'a pas été trouvé dans le fichier XML de l'enquête {doi}"
            raise MissingAttributeError(msg)

        # Get language
        codebook = soup.find("codeBook")
        data["lang"] = codebook.get("xml-lang", codebook.get("xml:lang", "")) if codebook else ""

        # Get all authors
        authors = []
        for author_element in soup.find_all("AuthEnty"):
            text_content = author_element.get_text(strip=True)
            affiliation = author_element.get("affiliation", "")
            authors.append(f"{text_content} ({affiliation})" if affiliation else text_content)
        data["authors"] = "; ".join(authors)

        # Get producer
        producer = soup.find("producer")
        data["producer"] = producer.text.strip() if producer else ""

        # Get distributor
        distributor = soup.find("distrbtr")
        data["distributor"] = distributor.text.strip() if distributor else ""

        # Find the <timePrd> tag with event="start"
        time_prd_start = soup.find("timePrd", attrs={"event": "start"})
        data["start_date"] = time_prd_start.get("date", "") if time_prd_start else ""

        # Get geographic coverage
        geographic_coverage = soup.find("nation")
        data["geographic_coverage"] = (
            geographic_coverage.get_text(strip=True) if geographic_coverage else ""
        )

        # Get geopgraphic unit
        geographic_unit = soup.find("geogCover")
        data["geographic_unit"] = geographic_unit.get_text(strip=True) if geographic_unit else ""

        # Get unit of analysis
        unit_of_analysis = soup.find("anlyUnit")
        data["unit_of_analysis"] = unit_of_analysis.get_text(strip=True) if unit_of_analysis else ""

        # Get contact
        contact = soup.find("contact")
        data["contact"] = contact.get("email", "") if contact else ""

        # Get date last version
        date_ver_stmt = None
        date_dist_stmt = None
        date_tag_dist_stmt = (
            soup.find("distStmt").find("distDate") if soup.find("distStmt") else None
        )
        if date_tag_dist_stmt and date_tag_dist_stmt.get("date"):
            date_dist_stmt = date_tag_dist_stmt.get("date")

        ver_stmt_tag = soup.find("verStmt")
        ver_stmt_tag_version = None
        if ver_stmt_tag:
            ver_stmt_tag_version = ver_stmt_tag.find("version")
        if ver_stmt_tag_version:
            if ver_stmt_tag_version.get("date"):
                date_ver_stmt = ver_stmt_tag_version.get("date").strip()
            elif ver_stmt_tag_version.get("type"):
                date_ver_stmt = ver_stmt_tag_version.get("type").strip()
            elif ver_stmt_tag_version.get("version"):
                date_ver_stmt = ver_stmt_tag_version.get("version").strip()
        data["date_last_version"] = (
            date_ver_stmt if date_ver_stmt else (date_dist_stmt if date_dist_stmt else "")
        )

        # Get all variables
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
        logger.error("Erreur lors de la lecture du DDI-C de l'enquête %s: %s", doi, str(e))
        raise e


def download_xml_file(survey_url):
    r = requests.get(survey_url, timeout=30)
    r.raise_for_status()

    return r.text
