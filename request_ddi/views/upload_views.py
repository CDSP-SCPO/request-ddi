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
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View

# -- LOCAL
from request_ddi.core.data_importer import import_data
from request_ddi.core.exceptions import DataImportError, PartialDataImportError
from request_ddi.core.forms import CSVUploadFormCollection
from request_ddi.core.models import (
    Survey,
)
from request_ddi.core.parser import parse_codebook_xml_file
from request_ddi.utils.timer import log_time
from request_ddi.utils.timing import timed
from request_ddi.views.mixins import StaffRequiredMixin

logger = logging.getLogger(__name__)
perf_logger = logging.getLogger("performance")


@method_decorator(log_time, name="dispatch")
class CSVUploadViewCollection(StaffRequiredMixin, View):
    template_name = "upload.html"
    form_class = CSVUploadFormCollection
    success_url = reverse_lazy("request_ddi:import")

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
    def form_valid(self, form):
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

            num_surveys, num_bindings, skipped_dois = self.process_data(
                survey_datas, xml_contents, skip_dois=duplicates
            )
            if skipped_dois:
                all_skipped = num_surveys == 0
                raise PartialDataImportError(
                    "Toutes les enquêtes existent déjà en base, aucun import effectué."
                    if all_skipped
                    else "Certaines enquêtes ont été ignorées car elles existent déjà.",
                    data=[
                        {
                            "num_surveys": num_surveys,
                            "num_bindings": num_bindings,
                        }
                    ],
                    errors=[f"Doublon ignoré : {doi}" for doi in skipped_dois],
                )
            return JsonResponse(
                {
                    "status": "success",
                    "message": f"Le fichier CSV a été traité avec succès. {num_surveys} enquête(s) et {num_bindings} binding(s) seront importée(s) ou mise(s) à jour.",
                    "data": [
                        {
                            "num_surveys": num_surveys,
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
        errors = []
        successful_surveys = []
        skipped_surveys = []
        num_surveys = 0
        total_bindings = 0

        for line_number, survey_data in enumerate(survey_datas, start=1):
            try:
                survey_doi = survey_data["doi"]
                if not survey_doi.startswith("doi:"):
                    msg = f"Le DOI à la ligne {line_number} n'est pas dans le bon format"
                    raise ValueError(msg)
                if survey_doi in skip_dois:
                    skipped_surveys.append(survey_doi)
                    continue

                # Conversion de survey_start_date en objet date (année uniquement)
                # DONOT create date object here as import_data function cannot accept any
                # arguments that are not serialisable. We just do the validation and stringify
                # the created object and then create object during DB object creation.
                if survey_data["start_date"]:
                    try:
                        # Tente de convertir la date au format "YYYY"
                        survey_data["start_date"] = str(
                            datetime.strptime(  # noqa: DTZ007
                                survey_data["start_date"], "%Y"
                            ).date()
                        )
                    except ValueError:
                        try:
                            # Si ça échoue, tente de convertir la date au format "YYYY-MM-DD"
                            survey_data["start_date"] = str(
                                datetime.strptime(  # noqa: DTZ007
                                    survey_data["start_date"], "%Y-%m-%d"
                                ).date()
                            )
                        except ValueError:
                            msg = f"L'année de début à la ligne {line_number} n'est pas valide : {survey_data['start_date']}"
                            raise ValueError(msg) from None

                else:
                    survey_data["start_date"] = None

                # Vérification et formatage de survey_date_last_version
                if survey_data["date_last_version"]:
                    len_format_yyyy_mm = 7
                    if len(survey_data["date_last_version"]) == len_format_yyyy_mm:
                        survey_data["date_last_version"] += "-01"
                    try:
                        survey_data["date_last_version"] = str(
                            datetime.strptime(  # noqa: DTZ007
                                survey_data["date_last_version"], "%Y-%m-%d"
                            ).date()
                        )
                    except ValueError:
                        msg = f"La date de la dernière version à la ligne {line_number} n'est pas valide : {survey_data['date_last_version']}"
                        raise ValueError(msg) from None

                else:
                    survey_data["date_last_version"] = None

                doi_formatted = survey_doi.replace("doi:", "", 1)
                xml_content = xml_contents.get(doi_formatted)
                if not xml_content:
                    msg = "Aucun XML fourni"
                    raise ValueError(msg)

                uploaded_file = io.BytesIO(xml_content.encode("utf-8"))

                ddic = parse_codebook_xml_file(uploaded_file)
                if ddic["variables"]:
                    if ddic["doi"] != survey_doi:
                        msg = f"Le XML téléchargé ne correspond pas à cette enquête (DOIs trouvés dans le XML : {ddic['doi']})"
                        raise ValueError(msg)
                else:
                    msg = "Le XML est vide ou invalide"
                    raise ValueError(msg)

                # Add survey variables to data
                survey_data["variables"] = ddic["variables"]

                # Submit tasks to background worker
                import_data.enqueue(survey_data)

                # Increment counters to send them back in the response
                successful_surveys.append(survey_doi)
                num_surveys += 1
                total_bindings += len(survey_data["variables"])

            except Exception as e:
                errors.append(
                    f"Ligne {line_number}, erreur pour l'enquête de DOI {survey_doi} : {e}"
                )

        if errors:
            if successful_surveys:
                msg = "Certaines enquêtes n'ont pas pu être traitées"
                raise PartialDataImportError(
                    msg,
                    data=[
                        {
                            "successful_surveys": successful_surveys,
                            "num_surveys": num_surveys,
                            "total_bindings": total_bindings,
                        }
                    ],
                    errors=errors,
                )
            else:
                msg = "Aucune enquête n'a pu être traitée"
                raise DataImportError(
                    msg,
                    errors=errors,
                )

        return num_surveys, total_bindings, skipped_surveys

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
    r = requests.get(survey_url, timeout=30)
    r.raise_for_status()

    return r.text
