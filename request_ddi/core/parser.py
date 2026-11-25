# -- STDLIB
import logging
import re

# -- THIRDPARTY
import charset_normalizer
import requests
from bs4 import BeautifulSoup
from lxml import etree

from request_ddi.utils.timing import timed

from .exceptions import (
    DDIXMLFileNotFoundError,
    InvalidDDICError,
    InvalidDOIError,
    MissingAttributeError,
    UnsupportedDDISchemaError,
)
from .identifiers import is_valid_survey_id
from .models import UploadedDDIXMLFile

logger = logging.getLogger(__name__)

_XML_ENCODING_DECLARATION_RE = re.compile(
    rb'<\?xml[^>]*encoding=["\']([^"\']+)["\']', re.IGNORECASE
)
_XML_DECLARATION_RE = re.compile(r"^\s*<\?xml[^>]*\?>")
_XML_XPATH_QUERY = "//*[local-name() = $name]"

DDI_SCHEMA_CODEBOOK = "ddic"
DDI_SCHEMA_LIFECYCLE = "ddil"

_DDI_NAMESPACE_PREFIXES = {
    "ddi:codebook:": DDI_SCHEMA_CODEBOOK,
    "ddi:instance:": DDI_SCHEMA_LIFECYCLE,
}


@timed
def fetch_and_parse_xml(data):
    try:
        survey_url = data.get("url", "").strip()
        content = (
            fetch_xml_from_remote(survey_url) if survey_url else fetch_xml_from_local(data["id"])
        )

        # The same import endpoint accepts DDI-C and DDI-L: pick the parser from the
        # schema namespace of the XML itself.
        schema = detect_ddi_schema(content)
        if schema == DDI_SCHEMA_LIFECYCLE:
            msg = "L'import de fichiers DDI-L (DDI-Lifecycle) n'est pas encore supporté."
            raise UnsupportedDDISchemaError(msg)
        parsed = parse_codebook_xml_file(content)

        # Check if Id in XML matches with the Id in CSV file
        if parsed["id"] != data["id"]:
            msg = f"Le XML téléchargé ne correspond pas à cette enquête (Ids trouvés dans le XML : {parsed['id']})"
            raise InvalidDDICError(msg)

        # Merge parsed XML data with survey study data
        data = {**data, **parsed}
        return data
    except Exception as e:
        logger.error(
            "Erreur lors de la récupération du DDI de l'enquête %s: %s", data["id"], str(e)
        )
        raise e


def detect_ddi_schema(content):
    """Retourne `DDI_SCHEMA_CODEBOOK` (DDI-C) ou `DDI_SCHEMA_LIFECYCLE` (DDI-L) selon
    l'espace de noms de l'élément racine du XML.

    Un XML sans espace de noms reconnu, ou illisible, est traité comme du DDI-C : le
    parser DDI-C se charge alors de remonter l'erreur précise (Id manquant, XML invalide...).
    Seul un espace de noms DDI-L déclenche le chemin DDI-L.
    """
    stripped = _XML_DECLARATION_RE.sub("", content, count=1)
    try:
        root = etree.fromstring(stripped.encode("utf-8"))
    except etree.XMLSyntaxError:
        return DDI_SCHEMA_CODEBOOK

    namespace = etree.QName(root).namespace or ""
    for prefix, schema in _DDI_NAMESPACE_PREFIXES.items():
        if namespace.startswith(prefix):
            return schema
    return DDI_SCHEMA_CODEBOOK


def decode_xml_content(raw_bytes, filename):
    """Décode le contenu brut d'un fichier XML uploadé.

    Priorité à l'encodage déclaré dans le prologue XML (`<?xml encoding="..."?>`),
    qui fait autorité pour ce format. À défaut de déclaration (ou si elle est
    invalide), on retombe sur une détection heuristique — mais celle-ci n'est pas
    fiable sur des textes courts avec peu de caractères non-ASCII, d'où la
    préférence pour la déclaration explicite quand elle existe.
    """
    declared = _XML_ENCODING_DECLARATION_RE.match(raw_bytes.lstrip()[:200])
    if declared:
        try:
            return raw_bytes.decode(declared.group(1).decode("ascii"))
        except (LookupError, UnicodeDecodeError):
            pass

    match = charset_normalizer.from_bytes(raw_bytes).best()
    if match is None:
        msg = f"Impossible de déterminer l'encodage du fichier {filename}"
        raise InvalidDDICError(msg)
    return str(match)


def extract_id_from_xml(content):
    """Extrait uniquement l'Id (DOI ou identifiant local `local:request/...`) d'un fichier XML DDI, via xpath (lxml), sans parser
    l'intégralité du codebook. Utile pour un DDI-L volumineux, où un parsing complet
    juste pour identifier le fichier serait inutilement coûteux.
    """
    # lxml refuse une déclaration d'encodage sur une str Python déjà décodée.
    stripped = _XML_DECLARATION_RE.sub("", content, count=1)
    try:
        root = etree.fromstring(stripped.encode("utf-8"))
    except etree.XMLSyntaxError as e:
        msg = f"Fichier XML invalide : {e}"
        raise InvalidDDICError(msg) from e

    # By default XPath looks up in default namespace. In our case, DDI has its dedicated
    # namespace which we need to include in the query. To avoid looking for type and
    # version of DDI to include in XPath query, we use local-name function which parses
    # the XML locally in its own namespace
    # Ref: https://examples.javacodegeeks.com/java-development/core-java/xml/xpath/xpath-local-name-example/
    for ele in root.xpath(_XML_XPATH_QUERY, name="IDNo"):
        if ele.text is None:
            continue
        survey_id = ele.text.strip()
        if is_valid_survey_id(survey_id):
            return survey_id

    msg = "Id introuvable"
    raise InvalidDOIError(msg)


def fetch_xml_from_local(survey_id):
    uploaded = UploadedDDIXMLFile.objects.filter(ddi_id=survey_id).first()
    if not uploaded:
        # Vaut aussi bien pour "jamais déposé" que pour "déjà importé" : la ligne est
        # supprimée dès qu'un import la consomme avec succès, donc les deux cas sont
        # indiscernables ici, volontairement — même erreur, même remède (redéposer).
        msg = (
            f"Aucun fichier XML n'a été déposé pour l'enquête {survey_id}. Déposez-le via la page "
            "d'import XML avant de relancer l'import."
        )
        raise DDIXMLFileNotFoundError(msg)
    return uploaded.xml_content


def parse_codebook_xml_file(content):  # noqa: PLR0915,C901
    """Parse un fichier XML et retourne les données extraites ou None s'il y a une erreur."""
    try:
        soup = BeautifulSoup(content, "xml")

        id_tag = soup.find("IDNo", attrs={"agency": "DataCite"}) or soup.find("IDNo")
        survey_id = id_tag.text.strip() if id_tag else None

        if not is_valid_survey_id(survey_id):
            msg = (
                f"Id {survey_id} invalide (doit commencer par 'doi:' ou être de la forme "
                "'local:request/<identifiant alphanumérique>')"
            )
            raise InvalidDOIError(msg)

        # Intialise data
        data = {"id": survey_id, "variables": []}

        # Get title
        title = soup.find("titl")
        data["title"] = title.text.strip() if title else ""
        if not data["title"]:
            msg = f"L'attribut titl n'a pas été trouvé dans le fichier XML de l'enquête {survey_id}"
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

        if not data["variables"]:
            msg = (
                f"Aucune variable (balise var) trouvée dans le fichier XML de l'enquête {survey_id}"
            )
            raise MissingAttributeError(msg)

        return data
    except Exception as e:
        logger.error("Erreur lors de la lecture du DDI-C de l'enquête %s: %s", survey_id, str(e))
        raise e


def fetch_xml_from_remote(survey_url):
    r = requests.get(survey_url, timeout=30)
    r.raise_for_status()

    return r.text
