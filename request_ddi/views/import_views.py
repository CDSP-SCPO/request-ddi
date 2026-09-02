# -- STDLIB
import logging

# -- THIRDPARTY
# -- DJANGO
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View

from request_ddi.core.data_importer import IMPORT_FORMAT_DDIC

# -- LOCAL
from request_ddi.core.forms import DDICImportFormCollection, DDICXMLUploadForm
from request_ddi.core.models import UploadedDDICFile
from request_ddi.core.parser import decode_xml_content, parse_codebook_xml_file
from request_ddi.utils.csv import read_csv_file
from request_ddi.utils.timer import log_time
from request_ddi.views.mixins import ImportViewMixin, StaffRequiredMixin

logger = logging.getLogger(__name__)
perf_logger = logging.getLogger("performance")


@method_decorator(log_time, name="dispatch")
class DDICImportViewCollection(StaffRequiredMixin, ImportViewMixin, View):
    template_name = "import_ddic.html"
    form_class = DDICImportFormCollection
    success_url = reverse_lazy("request_ddi:import_ddic")
    import_format = IMPORT_FORMAT_DDIC

    def get(self, request, *args, **kwargs):
        context = {"csv_form": self.form_class()}
        return render(request, self.template_name, context)

    def get_data(self, form):
        data = []
        for file in self.request.FILES.getlist("csv_file"):
            # This file has already been read in the clean_csv_file() method of
            # DDICImportFormCollection. So, we need to seek the file to the begining
            # to be able to read again
            file.seek(0)
            content = file.read().decode("utf-8").splitlines()
            for row in read_csv_file(content):
                data.append(row)
        return data


@method_decorator(log_time, name="dispatch")
class DDICXMLUploadView(StaffRequiredMixin, View):
    """Dépose un ou plusieurs fichiers DDI-C XML dans le volume, indexés par DOI.

    Une ligne CSV d'import (`DDICImportViewCollection`) dont la colonne `url` est
    vide sera résolue en cherchant ici le fichier correspondant au DOI, plutôt
    qu'en le téléchargeant.
    """

    form_class = DDICXMLUploadForm

    def post(self, request, *args, **kwargs):
        files = request.FILES.getlist("xml_files")
        if not files:
            return JsonResponse(
                {"status": "error", "message": "Aucun fichier XML sélectionné."}, status=400
            )

        uploaded_dois = []
        errors = []
        for file in files:
            if not file.name.endswith(".xml"):
                errors.append(f"{file.name} : le fichier doit être au format XML.")
                continue

            try:
                content = decode_xml_content(file.read(), file.name)
                ddic = parse_codebook_xml_file(content)

                doi = ddic["doi"]
                existing = UploadedDDICFile.objects.filter(doi=doi).first()
                if existing:
                    logger.warning(
                        "Écrasement du fichier XML du DOI %s : '%s' (déposé le %s) remplacé par '%s'",
                        doi,
                        existing.original_filename,
                        existing.uploaded_at,
                        file.name,
                    )

                UploadedDDICFile.objects.update_or_create(
                    doi=doi,
                    defaults={
                        "original_filename": file.name,
                        "xml_content": content,
                    },
                )
                uploaded_dois.append(doi)
            except Exception as e:
                errors.append(f"{file.name} : {e}")
                continue

        if not uploaded_dois:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "Aucun fichier n'a pu être déposé.",
                    "errors": errors,
                },
                status=400,
            )

        if errors:
            return JsonResponse(
                {
                    "status": "partial_success",
                    "message": f"{len(uploaded_dois)} fichier(s) déposé(s), {len(errors)} erreur(s).",
                    "data": [{"dois": uploaded_dois}],
                    "errors": errors,
                },
                status=207,
            )

        return JsonResponse(
            {
                "status": "success",
                "message": f"{len(uploaded_dois)} fichier(s) XML déposé(s) avec succès.",
                "data": [{"dois": uploaded_dois}],
            }
        )
