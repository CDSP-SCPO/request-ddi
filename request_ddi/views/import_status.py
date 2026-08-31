# request_ddi/views/import_status.py

import json
from datetime import timedelta

from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views import View
from django_tasks_db.models import DBTaskResult

from request_ddi.core.data_importer import import_data
from request_ddi.views.mixins import StaffRequiredMixin

# Résolu dynamiquement depuis la fonction décorée — ne peut pas se tromper
IMPORT_TASK_PATH = import_data.module_path
TASK_WINDOW_HOURS = 48  # Afficher les tâches des dernières 48h


class ImportStatusView(StaffRequiredMixin, View):
    template_name = "import_status.html"

    def get(self, request, *args, **kwargs):
        if request.headers.get("Accept") == "application/json":
            return self._json_response()
        return render(request, self.template_name)

    def _json_response(self):
        since = timezone.now() - timedelta(hours=TASK_WINDOW_HOURS)
        results = list(
            DBTaskResult.objects.filter(
                task_path=IMPORT_TASK_PATH,
                enqueued_at__gte=since,
            ).order_by("-enqueued_at")
        )

        # Construire un index DOI → tâche la plus récente pour savoir
        # si une tâche plus récente existe pour le même DOI.
        # Les résultats étant déjà triés par -enqueued_at, le premier
        # qu'on rencontre pour un DOI est le plus récent.
        most_recent_id_by_doi: dict[str, str] = {}
        for r in results:
            try:
                survey_data = r.args_kwargs.get("args", [None])[0]
                doi = survey_data.get("doi") if isinstance(survey_data, dict) else None
            except (IndexError, AttributeError, TypeError):
                doi = None
            if doi and doi not in most_recent_id_by_doi:
                most_recent_id_by_doi[doi] = str(r.id)

        tasks = []
        for r in results:
            doi = None
            survey_data_raw = None
            try:
                survey_data_raw = r.args_kwargs.get("args", [None])[0]
                if isinstance(survey_data_raw, dict):
                    doi = survey_data_raw.get("doi")
            except (IndexError, AttributeError, TypeError):
                pass

            # Durée d'exécution
            duration_seconds = None
            if r.started_at and r.finished_at:
                duration_seconds = round((r.finished_at - r.started_at).total_seconds(), 1)

            # Nb variables importées depuis return_value
            num_records = num_new_variables = num_new_bindings = None
            if r.return_value and isinstance(r.return_value, dict):
                num_records = r.return_value.get("num_records")
                num_new_variables = r.return_value.get("num_new_variables")
                num_new_bindings = r.return_value.get("num_new_bindings")

            # Traceback tronqué pour l'affichage
            traceback_excerpt = None
            if r.traceback:
                lines = r.traceback.strip().splitlines()
                traceback_excerpt = "\n".join(lines[-8:])

            # Bouton relancer : uniquement si FAILED et qu'aucune tâche
            # plus récente n'existe pour ce même DOI
            task_id = str(r.id)
            can_retry = (
                r.status == "FAILED"
                and doi is not None
                and most_recent_id_by_doi.get(doi) == task_id
            )

            tasks.append(
                {
                    "id": task_id,
                    "doi": doi,
                    "status": r.status,
                    "enqueued_at": r.enqueued_at.isoformat() if r.enqueued_at else None,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                    "duration_seconds": duration_seconds,
                    "num_records": num_records,
                    "num_new_variables": num_new_variables,
                    "num_new_bindings": num_new_bindings,
                    "exception_class": r.exception_class_path.rsplit(".", 1)[-1]
                    if r.exception_class_path
                    else None,
                    "traceback": traceback_excerpt,
                    "can_retry": can_retry,
                    # On passe le survey_data pour pouvoir le re-enqueue sans retaper le DOI
                    "_survey_data": survey_data_raw if can_retry else None,
                }
            )

        has_pending = any(t["status"] in ("READY", "RUNNING") for t in tasks)

        return JsonResponse(
            {
                "tasks": tasks,
                "has_pending": has_pending,
                "window_hours": TASK_WINDOW_HOURS,
            }
        )


class ImportRetryView(StaffRequiredMixin, View):
    """
    POST /import/status/retry/
    Body JSON : { "task_id": "<uuid>" }

    Récupère le survey_data de la tâche échouée et le re-enqueue.
    """

    def post(self, request, *args, **kwargs):  # noqa : PLR0911, C901
        try:
            body = json.loads(request.body)
            task_id = body.get("task_id")
        except (json.JSONDecodeError, AttributeError):
            return JsonResponse({"error": "Corps JSON invalide"}, status=400)

        if not task_id:
            return JsonResponse({"error": "task_id manquant"}, status=400)

        try:
            original = DBTaskResult.objects.get(id=task_id, task_path=IMPORT_TASK_PATH)
        except DBTaskResult.DoesNotExist:
            return JsonResponse({"error": "Tâche introuvable"}, status=404)

        if original.status != "FAILED":
            return JsonResponse(
                {"error": "Seules les tâches en échec peuvent être relancées"}, status=400
            )

        # Vérifier qu'il n'existe pas déjà une tâche plus récente pour ce DOI
        try:
            survey_data = original.args_kwargs["args"][0]
            doi = survey_data.get("doi") if isinstance(survey_data, dict) else None
        except (IndexError, KeyError, TypeError):
            return JsonResponse({"error": "Impossible de lire le survey_data"}, status=500)

        if doi:
            newer_exists = DBTaskResult.objects.filter(
                task_path=IMPORT_TASK_PATH,
                enqueued_at__gt=original.enqueued_at,
            ).exists()
            # Vérifier que la tâche plus récente concerne bien le même DOI
            if newer_exists:
                for r in DBTaskResult.objects.filter(
                    task_path=IMPORT_TASK_PATH,
                    enqueued_at__gt=original.enqueued_at,
                ):
                    try:
                        d = r.args_kwargs["args"][0].get("doi")
                    except Exception:
                        d = None
                    if d == doi:
                        return JsonResponse(
                            {"error": "Une tâche plus récente existe déjà pour ce DOI"},
                            status=409,
                        )

        import_data.enqueue(*original.args_kwargs["args"])

        return JsonResponse({"status": "enqueued", "doi": doi})
