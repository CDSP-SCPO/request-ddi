# -- STDLIB
import logging

# -- THIRDPARTY
# -- DJANGO
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View

from request_ddi.core.data_importer import IMPORT_FORMAT_DDIC

# -- LOCAL
from request_ddi.core.forms import DDICImportFormCollection
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
