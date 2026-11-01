from __future__ import annotations

from ssscreen_web.application.stages.condensation import CondensationStageRunner
from ssscreen_web.settings import get_settings
from ssscreen_web.workers.celery_app import celery_app
from ssscreen_web.workers.mp_dataset_task import prepare_dataset, recover_stale_dataset_tasks

runner = CondensationStageRunner()


@celery_app.task(name="ssscreen_web.condensation.batch", bind=True, acks_late=True)
def condense_batch(self, task_id: str, attempt_number: int | None = None) -> dict[str, object]:
    return prepare_dataset(self, task_id, attempt_number, runner)


def recover_stale_condensation_tasks() -> int:
    return recover_stale_dataset_tasks(
        task_type=runner.task_type,
        timeout_seconds=get_settings().mp_dataset_task_stale_seconds,
        error_message="The condensation worker stopped before reporting a terminal state",
    )
