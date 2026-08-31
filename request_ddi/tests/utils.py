import time

from django.tasks.backends.immediate import ImmediateBackend
from django.tasks.base import TaskResult, TaskResultStatus
from django.utils import timezone
from django.utils.json import normalize_json
from django_tasks_db.backend import DatabaseBackend
from django_tasks_db.models import DBTaskResult

STATUS_TIMEOUT = 5


class ImmediateDBBackend(ImmediateBackend, DatabaseBackend):
    """This task backend is exactly like ImmedidateBackend provided by Django core.
    ImmediateBackend does not enqueue tasks and executes them in blocking manner.
    However, in our implementation we do not check the result of the task in blocking
    manner and so there is no way to check the status of the executed task with
    ImmediateBackend.

    This custom backend address the above mentioned issue by mixing it with DatabaseBackend
    and storing the result of task in the DB. In the unit tests we check the latest
    task result, when relevant, to check the status of the task.
    """

    def enqueue(self, task, args, kwargs):
        self.validate_task(task)

        task_result = TaskResult(
            task=task,
            id=self._get_id(),
            status=TaskResultStatus.READY,
            enqueued_at=None,
            started_at=None,
            last_attempted_at=None,
            finished_at=None,
            args=args,
            kwargs=kwargs,
            backend=self.alias,
            errors=[],
            worker_ids=[],
        )

        self._execute_task(task_result)
        tracebacks = []
        for err in task_result.errors:
            tracebacks.append(err.traceback)

        DBTaskResult.objects.create(
            id=self._get_id(),
            args_kwargs=normalize_json({"args": args, "kwargs": kwargs}),
            priority=task.priority,
            task_path=task.module_path,
            queue_name=task.queue_name,
            run_after=task.run_after,  # type: ignore[misc]
            backend_name=self.alias,
            status=task_result.status,
            finished_at=timezone.now(),
            traceback="\n".join(tracebacks),
        )
        return task_result


def wait_task():
    """Return the status of latest Django task in the DB after waiting for task to finish"""
    start = time.time()
    while DBTaskResult.objects.latest("finished_at").status not in [
        TaskResultStatus.SUCCESSFUL,
        TaskResultStatus.FAILED,
    ]:
        time.sleep(1)
        if time.time() - start >= STATUS_TIMEOUT:
            return DBTaskResult.objects.latest("finished_at").status
    return DBTaskResult.objects.latest("finished_at").status, DBTaskResult.objects.latest(
        "finished_at"
    ).traceback
