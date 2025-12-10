# -- STDLIB
import csv
import logging
import re
from datetime import datetime

# -- THIRDPARTY
from bs4 import BeautifulSoup

# -- DJANGO
from django import forms
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.edit import FormView

# -- LOCAL
from request_ddi.core.data_importer import DataImporter
from request_ddi.core.forms import CSVUploadFormCollection, XMLUploadForm
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
class XMLUploadView(StaffRequiredMixin, FormView):
    template_name = "upload_xml.html"
    form_class = XMLUploadForm
    success_url = reverse_lazy("request_ddi:representedvariable_search")

    def handle_error(self, message, form=None):
        self.errors = getattr(self, "errors", [])
        self.errors.append(message)
        messages.error(self.request, message, extra_tags="safe")
        if form:
            return self.form_invalid(form)
        return None

    @timed
    @transaction.atomic
    def form_valid(self, form):
        self.errors = []  # Initialiser la liste des erreurs
        data = self.get_data(form)
        question_datas = list(self.convert_data(data))

        if self.errors:
            return self.form_invalid(form)

        importer = DataImporter()

        try:
            num_records, num_new_variables, num_new_bindings = importer.import_data(question_datas)

            # Récupérer les erreurs éventuelles après l'import
            if importer.errors:
                self.errors.extend(importer.errors)
                return self.form_invalid(form)

            messages.success(
                self.request,
                "Le fichier a été traité avec succès :<br/>"
                "<ul>"
                f"<li>{num_records} lignes ont été analysées.</li>"
                f"<li>{num_new_variables} nouvelles variables représentées créées.</li>"
                f"<li>{num_new_bindings} nouveaux bindings créés.</li>"
                "</ul>",
                extra_tags="safe",
            )
            return super().form_valid(form)

        except ValueError as ve:
            return self.handle_error(f"{ve}", form)

        except Exception as e:
            return self.handle_error(f"Erreur inattendue : {e!s}", form)

    def form_invalid(self, form):
        error_messages = []

        # 1. Erreurs Django du formulaire
        for field, field_errors in form.errors.items():  # noqa: B007
            for error in field_errors:
                cleaned_error = str(error)
                error_messages.append(cleaned_error)

        # 2. Erreurs collectées par self.errors (parser, import, etc.)
        error_messages.extend(getattr(self, "errors", []))

        if error_messages:
            messages.error(self.request, "<br/>".join(error_messages), extra_tags="safe")

        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.add_form_to_context(context)
        return context

    def add_form_to_context(self, context):
        context["xml_form"] = XMLUploadForm()

    def get_data(self, form):
        files = self.request.FILES.getlist("xml_file")
        self.errors = []
        return files

    def convert_data(self, files):
        results = []
        seen_invalid_dois = set()
        for file in files:
            perf_logger.debug(f"Début du traitement du fichier : {file.name}")
            try:
                parser = XMLParser()
                result = parser.parse_file(file, seen_invalid_dois)
                self.errors.extend(parser.errors)
                if result:
                    logger.info(f"{len(result)} variables extraites du fichier {file.name}")
                    results.extend(result)
            except Exception as e:
                error_msg = f"Erreur lors de la lecture du fichier {file.name}: {e!s}"
                self.errors.append(error_msg)
                logger.error(error_msg, exc_info=True)

        return results


@method_decorator(log_time, name="dispatch")
class CSVUploadViewCollection(StaffRequiredMixin, View):
    form_class = CSVUploadFormCollection

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST, request.FILES)
        if form.is_valid():
            return self.form_valid(form)
        else:
            return JsonResponse({"status": "error", "message": form.errors}, status=400)

    def form_valid(self, form):
        try:
            data = self.get_data(form)
            delimiter = form.cleaned_data["delimiter"]
            survey_datas = list(self.convert_data(data, delimiter))
            self.process_data(survey_datas)
            return JsonResponse(
                {
                    "status": "success",
                    "message": "Le fichier CSV a été importé avec succès.",
                }
            )
        except forms.ValidationError as ve:
            logger.error("Validation error: %s", ve.messages)
            return JsonResponse({"status": "error", "message": ve.messages})
        except IntegrityError as ie:
            doi = self.extract_doi_from_error(str(ie))
            if "unique constraint" in str(ie).lower():
                return JsonResponse(
                    {
                        "status": "error",
                        "message": f"Une enquête avec le DOI {doi} existe déjà dans la base de données.",
                    }
                )
        except ValueError as ve:
            return JsonResponse({"status": "error", "message": str(ve)})
        except Exception as e:
            return JsonResponse(
                {"status": "error", "message": "Le formulaire est invalide.", "errors": str(e)}
            )

    def get(self, request, *args, **kwargs):
        # Bloquer toute tentative d'accès GET, cette vue est POST uniquement
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    def get_data(self, form):
        # Utilisez les données décodées du formulaire
        return form.cleaned_data["decoded_csv"]

    def convert_data(self, content, delimiter):
        reader = csv.DictReader(content, delimiter=delimiter)
        return reader

    def extract_doi_from_error(self, error_message):
        match = re.search(r"\(external_ref\)=\((.*?)\)", error_message)
        return match.group(1) if match else "inconnu"

    @transaction.atomic
    def process_data(self, survey_datas):
        for line_number, row in enumerate(survey_datas, start=1):
            distributor_name = row["distributor"]
            distributor, created = Distributor.objects.get_or_create(name=distributor_name)

            collection_name = row["collection"]
            collection, created = Collection.objects.get_or_create(
                name=collection_name, distributor=distributor
            )

            subcollection_name = row["sous-collection"]
            subcollection, created = Subcollection.objects.get_or_create(  # noqa: RUF059
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

            Survey.objects.get_or_create(
                external_ref=survey_doi,
                name=survey_name,
                subcollection=subcollection,
                language=survey_language,
                author=survey_author,
                producer=survey_producer,
                start_date=survey_start_date,
                geographic_coverage=survey_geographic_coverage,
                geographic_unit=survey_geographic_unit,
                unit_of_analysis=survey_unit_of_analysis,
                contact=survey_contact,
                date_last_version=survey_date_last_version,
            )


@log_time
@csrf_exempt
@staff_required_json
def check_duplicates(request):
    if request.method == "POST":
        # Récupérer uniquement le fichier XML
        file = request.FILES.get("xml_file")

        if not file:
            return JsonResponse({"error": "Aucun fichier XML fourni"}, status=400)

        if not file.name.endswith(".xml"):
            return JsonResponse(
                {"error": "Format de fichier non supporté (seul le XML est accepté)"},
                status=400,
            )

        # Lecture et parsing du fichier XML
        decoded_file = file.read().decode("utf-8", errors="replace").splitlines()
        soup = BeautifulSoup("\n".join(decoded_file), "xml")
        existing_variables = []

        # Récupération du DOI / ID de l’enquête # noqa: RUF003
        id_tag = soup.find("IDNo", attrs={"agency": "DataCite"}) or soup.find("IDNo")
        if not id_tag or not id_tag.text.strip():
            return JsonResponse({"error": "IDNo manquant dans le fichier XML"}, status=400)

        variable_survey_id = id_tag.text.strip()

        # Recherche des doublons
        for var in soup.find_all("var"):
            variable_name = var.get("name", "").strip()
            if not variable_name:
                continue
            existing_bindings = BindingSurveyRepresentedVariable.objects.filter(
                variable_name=variable_name, survey__external_ref=variable_survey_id
            )
            if existing_bindings.exists():
                existing_variables.append(variable_name)

        if existing_variables:
            return JsonResponse({"status": "exists", "existing_variables": existing_variables})
        else:
            return JsonResponse({"status": "no_duplicates"})

    return JsonResponse({"error": "Requête invalide"}, status=400)
