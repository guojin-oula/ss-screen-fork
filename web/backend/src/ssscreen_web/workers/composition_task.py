from __future__ import annotations

from ssscreen_web.application.stages.composition import CompositionStageRunner
from ssscreen_web.settings import get_settings
from ssscreen_web.workers.celery_app import celery_app
from ssscreen_web.workers.mp_dataset_task import prepare_dataset, recover_stale_dataset_tasks

runner = CompositionStageRunner()


@celery_app.task(name="ssscreen_web.composition.screen", bind=True, acks_late=True)
def screen_composition(self, task_id: str, attempt_number: int | None = None) -> dict[str, object]:
    return prepare_dataset(self, task_id, attempt_number, runner)


def recover_stale_composition_tasks() -> int:
    return recover_stale_dataset_tasks(
        task_type=runner.task_type,
        timeout_seconds=get_settings().mp_dataset_task_stale_seconds,
        error_message="The composition worker stopped before reporting a terminal state",
    )
