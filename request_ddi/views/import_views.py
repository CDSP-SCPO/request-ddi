# -- STDLIB
import logging
import zipfile

# -- THIRDPARTY
# -- DJANGO
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View

# -- LOCAL
from request_ddi.core.forms import DDIImportForm, DDIXMLUploadForm
from request_ddi.core.models import UploadedDDIXMLFile
from request_ddi.core.parser import decode_xml_content, extract_id_from_xml
from request_ddi.utils.csv import read_csv_file
from request_ddi.utils.timer import log_time
from request_ddi.views.mixins import ImportViewMixin, StaffRequiredMixin

logger = logging.getLogger(__name__)
perf_logger = logging.getLogger("performance")


@method_decorator(log_time, name="dispatch")
class DDIImportView(StaffRequiredMixin, ImportViewMixin, View):
    template_name = "import_ddi.html"
    form_class = DDIImportForm
    success_url = reverse_lazy("request_ddi:import_ddi")

    def get(self, request, *args, **kwargs):
        context = {"csv_form": self.form_class()}
        return render(request, self.template_name, context)

    def get_data(self, form):
        data = []
        for file in self.request.FILES.getlist("csv_file"):
            # This file has already been read in the clean_csv_file() method of
            # DDIImportForm. So, we need to seek the file to the begining
            # to be able to read again
            file.seek(0)
            content = file.read().decode("utf-8").splitlines()
            for row in read_csv_file(content):
                data.append(row)
        return data


@method_decorator(log_time, name="dispatch")
class DDIXMLUploadView(StaffRequiredMixin, View):
    """Dépose un ou plusieurs fichiers DDI XML dans la DB, indexés par Id.

    Une ligne CSV d'import (`DDIImportView`) dont la colonne `url` est
    vide sera résolue en cherchant ici le fichier correspondant à l'Id, plutôt
    qu'en le téléchargeant.
    """

    form_class = DDIXMLUploadForm

    def handle_xml_file(self, file):
        content = decode_xml_content(file.read(), file.name)
        ddi_id = extract_id_from_xml(content)

        existing = UploadedDDIXMLFile.objects.filter(ddi_id=ddi_id).first()
        if existing:
            logger.warning(
                "Écrasement du fichier XML de l'Id %s : '%s' (déposé le %s) remplacé par '%s'",
                ddi_id,
                existing.original_filename,
                existing.uploaded_at,
                file.name,
            )

        UploadedDDIXMLFile.objects.update_or_create(
            ddi_id=ddi_id,
            defaults={
                "original_filename": file.name,
                "xml_content": content,
            },
        )
        return ddi_id

    def handle_zip_file(self, zip_file):
        ids = []
        errors = []
        # Open the zip file in read mode
        with zipfile.ZipFile(zip_file, mode="r") as archive:
            # Iterate over all files in the zip, processing each one independently so
            # that a single bad entry doesn't discard Ids already imported from this
            # zip nor skip the remaining entries.
            for file in archive.namelist():
                if not file.lower().endswith(".xml"):
                    continue
                try:
                    ids.append(self.handle_xml_file(archive.open(file, "r")))
                except Exception as e:
                    errors.append(f"{zip_file.name}/{file} : {e}")
        return ids, errors

    def post(self, request, *args, **kwargs):
        files = request.FILES.getlist("xml_files")
        if not files:
            return JsonResponse(
                {"status": "error", "message": "Aucun fichier XML sélectionné."}, status=400
            )

        uploaded_ids = []
        errors = []
        for file in files:
            try:
                if file.name.lower().endswith(".zip"):
                    zip_ids, zip_errors = self.handle_zip_file(file)
                    uploaded_ids.extend(zip_ids)
                    errors.extend(zip_errors)
                elif file.name.lower().endswith(".xml"):
                    uploaded_ids.append(self.handle_xml_file(file))
                else:
                    errors.append(f"{file.name} : le fichier doit être au format XML ou zip.")
                    continue
            except Exception as e:
                errors.append(f"{file.name} : {e}")
                continue

        if not uploaded_ids:
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
                    "message": f"{len(uploaded_ids)} fichier(s) déposé(s), {len(errors)} erreur(s).",
                    "data": [{"ids": uploaded_ids}],
                    "errors": errors,
                },
                status=207,
            )

        return JsonResponse(
            {
                "status": "success",
                "message": f"{len(uploaded_ids)} fichier(s) XML déposé(s) avec succès.",
                "data": [{"ids": uploaded_ids}],
            }
        )
