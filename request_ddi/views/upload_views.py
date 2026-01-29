# -- STDLIB
import csv
import io
import logging
import re
from datetime import datetime

import requests

# -- THIRDPARTY
from bs4 import BeautifulSoup

# -- DJANGO
from django import forms
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

# -- LOCAL
from request_ddi.core.data_importer import DataImporter
from request_ddi.core.forms import CSVUploadFormCollection
from request_ddi.core.models import (
    BindingSurveyRepresentedVariable,
    Collection,
    Distributor,
    Subcollection,
    Survey,
)
from request_ddi.core.parser import XMLParser
from request_ddi.utils.timer import log_time
from request_ddi.utils.timing import timed
from request_ddi.views.mixins import StaffRequiredMixin, staff_required_json

logger = logging.getLogger(__name__)
perf_logger = logging.getLogger("performance")


@method_decorator(log_time, name="dispatch")
class CSVUploadViewCollection(StaffRequiredMixin, View):
    template_name = "upload.html"
    form_class = CSVUploadFormCollection
    success_url = reverse_lazy("request_ddi:upload_csv_collection")

    def get(self, request, *args, **kwargs):
        context = {"csv_form": self.form_class()}
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST, request.FILES)

        if not form.is_valid():
            error_messages = []
            for field, errors in form.errors.items():
                for error in errors:
                    error_messages.append(f"{field}: {error}")

            return JsonResponse(
                {
                    "status": "error",
                    "message": " | ".join(error_messages)
                    if error_messages
                    else "Le formulaire est invalide.",
                },
                status=400,
            )

        # Formulaire valide, traiter les données
        return self.form_valid(form)

    @timed
    @transaction.atomic
    def form_valid(self, form):
        """Traite le CSV et les XMLs associés - RETOURNE TOUJOURS JSON"""
        try:
            data = self.get_data(form)
            delimiter = form.cleaned_data["delimiter"]
            survey_datas = list(self.convert_data(data, delimiter))
            num_surveys, num_variables, num_bindings = self.process_data(survey_datas, self.request)

            return JsonResponse(
                {
                    "status": "success",
                    "message": f"Le fichier CSV a été importé avec succès. "
                    f"{num_surveys} enquête(s), {num_variables} variable(s), "
                    f"{num_bindings} binding(s) créé(s).",
                    "num_surveys": num_surveys,
                    "num_variables": num_variables,
                    "num_bindings": num_bindings,
                }
            )

        except forms.ValidationError as ve:
            logger.error("Validation error: %s", ve.messages)
            return JsonResponse(
                {
                    "status": "error",
                    "message": " | ".join(ve.messages)
                    if isinstance(ve.messages, list)
                    else str(ve.messages),
                },
                status=400,
            )

        except IntegrityError as ie:
            doi = self.extract_doi_from_error(str(ie))
            if "unique constraint" in str(ie).lower():
                return JsonResponse(
                    {
                        "status": "error",
                        "message": f"Une enquête avec le DOI {doi} existe déjà dans la base de données.",
                    },
                    status=400,
                )
            return JsonResponse(
                {"status": "error", "message": f"Erreur d'intégrité de base de données: {ie!s}"},
                status=400,
            )

        except ValueError as ve:
            logger.error("ValueError: %s", str(ve))
            return JsonResponse({"status": "error", "message": str(ve)}, status=400)

        except Exception as e:
            logger.exception("Erreur inattendue lors de l'import")
            return JsonResponse(
                {"status": "error", "message": f"Erreur inattendue : {e!s}"}, status=500
            )

    def get_data(self, form):
        return form.cleaned_data["decoded_csv"]

    def convert_data(self, content, delimiter):
        reader = csv.DictReader(content, delimiter=delimiter)
        return reader

    def extract_doi_from_error(self, error_message):
        match = re.search(r"\(external_ref\)=\((.*?)\)", error_message)
        return match.group(1) if match else "inconnu"

    @transaction.atomic
    def process_data(self, survey_datas, request):  # noqa: PLR0915, PLR0912, C901
        importer = DataImporter()
        xml_parser = XMLParser()
        errors = []
        num_surveys = 0
        total_variables = 0
        total_bindings = 0
        xml_contents = request.session.get("xml_contents", {})

        for line_number, row in enumerate(survey_datas, start=1):
            distributor_name = row["distributor"]
            distributor, created = Distributor.objects.get_or_create(name=distributor_name)

            collection_name = row["collection"]
            collection, created = Collection.objects.get_or_create(
                name=collection_name, distributor=distributor
            )

            subcollection_name = row["sous-collection"]
            subcollection, created = Subcollection.objects.get_or_create(
                name=subcollection_name, collection=collection
            )

            survey_doi = row["doi"]
            if not survey_doi.startswith("doi:"):
                msg = f"Le DOI à la ligne {line_number} n'est pas dans le bon format : {survey_doi}"
                raise ValueError(msg)
            survey_name = row["title"]
            survey_language = row["xml_lang"]
            survey_author = row["author"]
            survey_producer = row["producer"]
            survey_start_date = row["start_date"]
            survey_geographic_coverage = row["geographic_coverage"]
            survey_geographic_unit = row["geographic_unit"]
            survey_unit_of_analysis = row["unit_of_analysis"]
            survey_contact = row["contact"]
            survey_date_last_version = row["date_last_version"]

            # Conversion de survey_start_date en objet date (année uniquement)
            if survey_start_date:
                try:
                    # Tente de convertir la date au format "YYYY"
                    survey_start_date = datetime.strptime(  # noqa: DTZ007
                        survey_start_date, "%Y"
                    ).date()
                except ValueError:
                    try:
                        # Si ça échoue, tente de convertir la date au format "YYYY-MM-DD"
                        survey_start_date = datetime.strptime(  # noqa: DTZ007
                            survey_start_date, "%Y-%m-%d"
                        ).date()
                    except ValueError:
                        msg = f"L'année de début à la ligne {line_number} n'est pas valide : {survey_start_date}"
                        raise ValueError(msg) from None

            else:
                survey_start_date = None
            # Vérification et formatage de survey_date_last_version
            if survey_date_last_version:
                len_format_yyyy_mm = 7
                if len(survey_date_last_version) == len_format_yyyy_mm:
                    survey_date_last_version += "-01"
                try:
                    survey_date_last_version = datetime.strptime(  # noqa: DTZ007
                        survey_date_last_version, "%Y-%m-%d"
                    ).date()
                except ValueError:
                    msg = f"La date de la dernière version à la ligne {line_number} n'est pas valide : {survey_date_last_version}"
                    raise ValueError(msg) from None

            else:
                survey_date_last_version = None

            survey, created = Survey.objects.get_or_create(  # noqa: RUF059
                external_ref=survey_doi,
                defaults={
                    "name": survey_name,
                    "subcollection": subcollection,
                    "language": survey_language,
                    "author": survey_author,
                    "producer": survey_producer,
                    "start_date": survey_start_date,
                    "geographic_coverage": survey_geographic_coverage,
                    "geographic_unit": survey_geographic_unit,
                    "unit_of_analysis": survey_unit_of_analysis,
                    "contact": survey_contact,
                    "date_last_version": survey_date_last_version,
                },
            )
            if created:
                num_surveys += 1
            doi_formatted = survey_doi.replace("doi:", "", 1)
            xml_content = xml_contents.get(doi_formatted)
            if not xml_content:
                errors.append(f"Aucun XML fourni pour le DOI {survey_doi}")
                continue

            uploaded_file = io.BytesIO(xml_content.encode("utf-8"))

            try:
                question_data = xml_parser.parse_file(uploaded_file, seen_invalid_dois=set())
                if question_data:
                    num_records, num_variables, num_bindings = importer.import_data(question_data)  # noqa: RUF059
                    total_variables += num_variables
                    total_bindings += num_bindings
            except Exception as e:
                errors.append(f"Erreur à la ligne {line_number} ({survey_doi}): {e}")

        if "xml_contents" in request.session:
            del request.session["xml_contents"]

        if errors:
            raise ValueError(" \n".join(errors))

        return num_surveys, total_variables, total_bindings


@log_time
@csrf_exempt
@staff_required_json
def check_duplicates(request):  # noqa: C901
    if request.method != "POST":
        return JsonResponse({"error": "Requête invalide"}, status=400)

    file = request.FILES.get("csv_file")
    if not file:
        return JsonResponse({"error": "Aucun fichier CSV fourni"}, status=400)

    if not file.name.endswith(".csv"):
        return JsonResponse(
            {"error": "Format de fichier non supporté (CSV attendu)"},
            status=400,
        )

    decoded_file = file.read().decode("utf-8", errors="replace").splitlines()
    sample = "\n".join(decoded_file[:2])  # Prendre les 2 premières lignes
    sniffer = csv.Sniffer()
    delimiter = sniffer.sniff(sample).delimiter
    reader = csv.DictReader(decoded_file, delimiter=delimiter)
    duplicates = {}
    xml_contents = {}

    for row in reader:
        survey_doi = row.get("doi", "").strip()
        if not survey_doi.startswith("doi:"):
            continue

        doi_formatted = survey_doi.replace("doi:", "", 1)

        try:
            file_id = find_xml_file_id(doi_formatted)
            if not file_id:
                continue  # pas de XML, on skip

            xml_content = download_xml_file(file_id)
            xml_contents[doi_formatted] = xml_content

            soup = BeautifulSoup(xml_content, "xml")
            variable_names = []
            for var in soup.find_all("var"):
                variable_name = var.get("name", "").strip()
                if not variable_name:
                    continue
                variable_names.append(variable_name)

            duplicates[survey_doi] = BindingSurveyRepresentedVariable.objects.filter(
                variable_name__in=variable_names, survey__external_ref__in=[survey_doi]
            ).exists()

        except Exception as e:
            logger.error("Erreur récupération XML %s: %s", survey_doi, e)
            continue
    request.session["xml_contents"] = xml_contents
    if duplicates:
        return JsonResponse(
            {
                "status": "duplicates",
                "duplicates": duplicates,
            }
        )

    return JsonResponse({"status": "ok"})


def find_xml_file_id(doi):
    url = "https://data.sciencespo.fr/api/datasets/:persistentId"
    params = {"persistentId": f"doi:{doi}"}

    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()

    files = r.json()["data"]["latestVersion"]["files"]

    for f in files:
        df = f["dataFile"]

        if (
            df.get("contentType") == "application/xml"
            or df.get("originalFileFormat", "").lower() == "ddi"
            or df.get("filename", "").lower().endswith(".xml")
        ):
            return df["id"]

    return None


def download_xml_file(file_id):
    url = f"https://data.sciencespo.fr/api/access/datafile/{file_id}"

    r = requests.get(url, timeout=30)
    r.raise_for_status()

    return r.text
