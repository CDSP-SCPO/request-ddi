import logging
from functools import wraps

# -- THIRDPARTY
# -- DJANGO
from django import forms
from django.contrib.auth.mixins import AccessMixin
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse

# -- LOCAL
from request_ddi.core.data_importer import import_data
from request_ddi.core.exceptions import (
    DataImportError,
    InvalidDOIError,
    PartialDataImportError,
)
from request_ddi.core.models import (
    Survey,
)
from request_ddi.utils.timing import timed

logger = logging.getLogger(__name__)


class StaffRequiredMixin(AccessMixin):
    """Mixin pour n'autoriser que les utilisateurs staff."""

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated or not user.is_staff:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


def staff_required_json(view_func):
    """Décorateur pour les vues API : renvoie du JSON."""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated or not user.is_staff:
            return JsonResponse({"error": "Accès interdit"}, status=403)
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def staff_required_html(view_func):
    """Décorateur pour les vues web : redirige vers login ou page interdite."""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect(f"{reverse('request_ddi:login')}?next={request.path}")
        if not user.is_staff:
            return redirect("forbidden")
        return view_func(request, *args, **kwargs)

    return _wrapped_view


class ImportViewMixin:
    """Mixin for importing data using DDI-C and native CSV formats"""

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
            survey_datas = self.get_data(form)

            duplicates = set()
            if not force_import:
                duplicates = self.check_duplicates(survey_datas)

            num_surveys, skipped_dois = self.process_data(survey_datas, skip_dois=duplicates)
            if skipped_dois:
                all_skipped = num_surveys == 0
                raise PartialDataImportError(
                    "Toutes les enquêtes existent déjà en base, aucun import effectué."
                    if all_skipped
                    else "Certaines enquêtes ont été ignorées car elles existent déjà.",
                    data=[
                        {
                            "num_surveys": num_surveys,
                        }
                    ],
                    errors=[f"Doublon ignoré : {doi}" for doi in skipped_dois],
                )
            return JsonResponse(
                {
                    "status": "success",
                    "message": f"Le fichier CSV a été traité avec succès. {num_surveys} enquête(s) seront importée(s) ou mise(s) à jour.",
                    "data": [
                        {
                            "num_surveys": num_surveys,
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

    def process_data(self, survey_datas, skip_dois=None):
        skip_dois = skip_dois or set()
        errors = []
        successful_surveys = []
        skipped_surveys = []
        num_surveys = 0

        for survey_data in survey_datas:
            try:
                survey_doi = survey_data["doi"]
                if not survey_doi.startswith("doi:"):
                    msg = f"Le DOI {survey_doi} n'est pas dans le bon format"
                    raise InvalidDOIError(msg)
                if survey_doi in skip_dois:
                    skipped_surveys.append(survey_doi)
                    continue

                # Submit tasks to background worker
                import_data.enqueue(survey_data, self.import_format)

                # Increment counters to send them back in the response
                successful_surveys.append(survey_doi)
                num_surveys += 1

            except Exception as e:
                errors.append(f"Erreur pour l'enquête de DOI {survey_doi} : {e}")

        if errors:
            if successful_surveys:
                msg = "Certaines enquêtes n'ont pas pu être traitées"
                raise PartialDataImportError(
                    msg,
                    data=[
                        {
                            "successful_surveys": successful_surveys,
                            "num_surveys": num_surveys,
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

        return num_surveys, skipped_surveys

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
