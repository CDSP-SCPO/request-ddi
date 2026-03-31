# -- STDLIB
import csv
import io
import logging
import re
from datetime import datetime

import requests

# -- THIRDPARTY
# -- DJANGO
from django import forms
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View

# -- LOCAL
from request_ddi.core.data_importer import DataImporter
from request_ddi.core.exceptions import DataImportError, PartialDataImportError
from request_ddi.core.forms import CSVUploadFormCollection
from request_ddi.core.models import (
    Collection,
    Distributor,
    Subcollection,
    Survey,
)
from request_ddi.core.parser import XMLParser
from request_ddi.utils.timer import log_time
from request_ddi.utils.timing import timed
from request_ddi.views.mixins import StaffRequiredMixin

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
    def form_valid(self, form):  # noqa: PLR0911
        """Traite le CSV et les XMLs associés - RETOURNE TOUJOURS JSON"""
        try:
            force_import = self.request.POST.get("force_import") == "on"
            data = self.get_data(form)
            delimiter = form.cleaned_data["delimiter"]
            survey_datas = list(self.convert_data(data, delimiter))
            xml_contents = self.load_xml_contents(survey_datas)

            duplicates = set()
            if not force_import:
                duplicates = self.check_duplicates(survey_datas)

            num_surveys, num_variables, num_bindings, skipped_dois = self.process_data(
                survey_datas, xml_contents, skip_dois=duplicates
            )
            if skipped_dois:
                all_skipped = num_surveys == 0 and num_variables == 0
                raise PartialDataImportError(
                    "Toutes les enquêtes existent déjà en base, aucun import effectué."
                    if all_skipped
                    else "Certaines enquêtes ont été ignorées car elles existent déjà.",
                    data=[
                        {
                            "num_surveys": num_surveys,
                            "total_variables": num_variables,
                            "total_bindings": num_bindings,
                        }
                    ],
                    errors=[f"Doublon ignoré : {doi}" for doi in skipped_dois],
                )
            return JsonResponse(
                {
                    "status": "success",
                    "message": f"Le fichier CSV a été importé avec succès. {num_surveys} enquête(s), {num_variables} variable(s), {num_bindings} binding(s) créé(s).",
                    "data": [
                        {
                            "num_surveys": num_surveys,
                            "num_variables": num_variables,
                            "num_bindings": num_bindings,
                        }
                    ],
                }
            )
        except PartialDataImportError as pe:
            return JsonResponse(
                {
                    "status": "partial_success",
                    "message": pe.message,
                    "data": pe.data,
                    "errors": pe.errors,
                },
                status=207,
            )

        except DataImportError as de:
            return JsonResponse(
                {
                    "status": "error",
                    "message": de.message,
                    "errors": de.errors,
                },
                status=400,
            )

        except forms.ValidationError as ve:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "La validation du formulaire a échouée",
                    "errors": ve.messages if isinstance(ve.messages, list) else [ve.messages],
                },
                status=400,
            )

        except IntegrityError as ie:
            doi = self.extract_doi_from_error(str(ie))
            if "unique constraint" in str(ie).lower():
                return JsonResponse(
                    {
                        "status": "error",
                        "message": "Erreur d'ajout de l'enquête dans la DB",
                        "errors": [
                            f"Une enquête avec le DOI {doi} existe déjà dans la base de données."
                        ],
                    },
                    status=400,
                )
            return JsonResponse(
                {
                    "status": "error",
                    "message": "Erreur d'intégrité de base de données",
                    "errors": [str(ie)],
                },
                status=400,
            )

        except Exception as e:
            logger.exception("Erreur inattendue lors de l'import")
            return JsonResponse(
                {
                    "status": "error",
                    "message": "Erreur inattendue",
                    "errors": [str(e)],
                },
                status=500,
            )

    def get_data(self, form):
        return form.cleaned_data["decoded_csv"]

    def convert_data(self, content, delimiter):
        reader = csv.DictReader(content, delimiter=delimiter)
        return reader

    def extract_doi_from_error(self, error_message):
        match = re.search(r"\(external_ref\)=\((.*?)\)", error_message)
        return match.group(1) if match else "inconnu"

    def process_data(self, survey_datas, xml_contents, skip_dois=None):  # noqa: PLR0915, PLR0912, C901
        skip_dois = skip_dois or set()
        importer = DataImporter()
        xml_parser = XMLParser()
        errors = []
        successful_surveys = []
        skipped_surveys = []
        num_surveys = 0
        total_variables = 0
        total_bindings = 0

        for line_number, row in enumerate(survey_datas, start=1):
            try:
                survey_doi = row["doi"]
                if not survey_doi.startswith("doi:"):
                    msg = f"Le DOI à la ligne {line_number} n'est pas dans le bon format"
                    raise ValueError(msg)
                if survey_doi in skip_dois:
                    skipped_surveys.append(survey_doi)
                    continue
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

                doi_formatted = survey_doi.replace("doi:", "", 1)
                xml_content = xml_contents.get(doi_formatted)
                if not xml_content:
                    msg = "Aucun XML fourni"
                    raise ValueError(msg)

                uploaded_file = io.BytesIO(xml_content.encode("utf-8"))

                question_data = xml_parser.parse_file(uploaded_file, seen_invalid_dois=set())
                if question_data:
                    doi_found_in_xml = question_data[0][0]
                    expected_doi = survey_doi
                    if doi_found_in_xml != expected_doi:
                        msg = f"Le XML téléchargé ne correspond pas à cette enquête (DOIs trouvés dans le XML : {doi_found_in_xml})"
                        raise ValueError(msg)
                else:
                    msg = "Le XML est vide ou invalide"
                    raise ValueError(msg)

                with transaction.atomic():
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

                    num_records, num_variables, num_bindings = importer.import_data(  # noqa: RUF059
                        question_data,
                    )
                    total_variables += num_variables
                    total_bindings += num_bindings
                    successful_surveys.append(survey_doi)

            except Exception as e:
                errors.append(
                    f"Ligne {line_number}, erreur pour l'enquête de DOI {survey_doi} : {e}"
                )

        if errors:
            if successful_surveys:
                msg = "Certaines enquêtes n'ont pas pu être importées"
                raise PartialDataImportError(
                    msg,
                    data=[
                        {
                            "successful_surveys": successful_surveys,
                            "num_surveys": num_surveys,
                            "total_variables": total_variables,
                            "total_bindings": total_bindings,
                        }
                    ],
                    errors=errors,
                )
            else:
                msg = "Aucune enquête n'a pu être importée"
                raise DataImportError(
                    msg,
                    errors=errors,
                )

        return num_surveys, total_variables, total_bindings, skipped_surveys

    def check_duplicates(self, survey_datas):
        """Vérifie si des enquêtes du CSV existent déjà en base."""
        duplicates = []
        for row in survey_datas:
            survey_doi = row.get("doi", "").strip()
            if not survey_doi.startswith("doi:"):
                continue
            try:
                if Survey.objects.filter(external_ref=survey_doi).exists():
                    duplicates.append(survey_doi)
            except Exception as e:
                logger.error("Erreur récupération XML %s: %s", survey_doi, e)
                continue
        return duplicates

    def load_xml_contents(self, survey_datas):
        xml_contents = {}
        for row in survey_datas:
            survey_doi = row.get("doi", "").strip()
            doi_formatted = survey_doi.replace("doi:", "", 1)
            survey_url = row.get("url", "").strip()
            if not survey_url:
                continue
            try:
                xml_contents[doi_formatted] = download_xml_file(survey_url)
            except Exception as e:
                logger.error("Erreur téléchargement XML %s: %s", survey_doi, e)
        return xml_contents


def download_xml_file(survey_url):
    url = f"{survey_url}"

    r = requests.get(url, timeout=30)
    r.raise_for_status()

    return r.text
