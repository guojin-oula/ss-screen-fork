from __future__ import annotations

import socket
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from celery.utils.log import get_task_logger
from sqlalchemy import select

from ssscreen_web.application.stages.base import StageRunner, TaskContext
from ssscreen_web.application.stages.mp_dataset import MPOfflineDatasetRunner
from ssscreen_web.domain.enums import AttemptStatus, RunStatus, TaskStatus
from ssscreen_web.domain.errors import DomainError
from ssscreen_web.domain.transitions import ensure_run_transition, ensure_task_transition
from ssscreen_web.infrastructure.artifacts import FileSystemArtifactStore
from ssscreen_web.infrastructure.database import get_session_factory
from ssscreen_web.infrastructure.models import Artifact, Attempt, Dataset, Run, Task
from ssscreen_web.settings import get_settings
from ssscreen_web.workers.celery_app import celery_app
from ssscreen_web.workers.example_task import _add_event, _finish_cancelled

logger = get_task_logger(__name__)
runner = MPOfflineDatasetRunner()


def _cleanup_stage_inputs(
    stage_runner: StageRunner, *, configuration: dict[str, object], settings
) -> None:
    try:
        stage_runner.cleanup(
            TaskContext(
                configuration=configuration,
                sandbox=settings.attempt_sandbox_root,
                settings=settings,
            )
        )
    except Exception:
        logger.warning("Dataset input cleanup failed", exc_info=True)


def prepare_dataset(
    celery_task,
    task_id: str,
    attempt_number: int | None,
    stage_runner: StageRunner,
) -> dict[str, object]:
    parsed_task_id = uuid.UUID(task_id)
    settings = get_settings()
    store = FileSystemArtifactStore(settings.artifact_root)
    store.ensure_ready()
    FileSystemArtifactStore(settings.attempt_sandbox_root).ensure_ready()

    with get_session_factory()() as session:
        task = session.scalar(select(Task).where(Task.id == parsed_task_id).with_for_update())
        if task is None or task.task_type != stage_runner.task_type:
            return {"status": "missing"}
        run = session.scalar(select(Run).where(Run.id == task.run_id).with_for_update())
        latest_attempt = session.scalar(
            select(Attempt)
            .where(Attempt.task_id == task.id)
            .order_by(Attempt.number.desc())
            .limit(1)
            .with_for_update()
        )
        if latest_attempt is None:
            return {"status": "missing_attempt", "task_id": task_id}
        selected_number = attempt_number or latest_attempt.number
        attempt = session.scalar(
            select(Attempt)
            .where(Attempt.task_id == task.id, Attempt.number == selected_number)
            .with_for_update()
        )
        if attempt is None:
            return {"status": "missing_attempt", "task_id": task_id}
        if attempt.id != latest_attempt.id:
            return {"status": "superseded", "task_id": task_id, "attempt_number": selected_number}
        if task.status in {TaskStatus.SUCCEEDED, TaskStatus.CANCELLED} or attempt.status in {
            AttemptStatus.SUCCEEDED,
            AttemptStatus.FAILED,
            AttemptStatus.CANCELLED,
        }:
            if task.status == TaskStatus.CANCELLED:
                _cleanup_stage_inputs(
                    stage_runner,
                    configuration=dict(run.configuration),
                    settings=settings,
                )
            return {"status": "duplicate", "task_id": task_id}
        if task.status == TaskStatus.RUNNING and attempt.status == AttemptStatus.RUNNING:
            return {"status": "active", "task_id": task_id}
        if task.status == TaskStatus.CANCEL_REQUESTED:
            configuration = dict(run.configuration)
            _finish_cancelled(session, run=run, task=task, attempt=attempt)
            session.commit()
            _cleanup_stage_inputs(stage_runner, configuration=configuration, settings=settings)
            return {"status": "cancelled"}
        if task.status != TaskStatus.QUEUED or attempt.status != AttemptStatus.QUEUED:
            return {"status": "ignored", "task_id": task_id}

        ensure_task_transition(TaskStatus.QUEUED, TaskStatus.RUNNING)
        previous_run_status = RunStatus(run.status)
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(UTC)
        attempt.status = AttemptStatus.RUNNING
        attempt.worker_id = f"{socket.gethostname()}:{celery_task.request.id or 'direct'}"
        attempt.started_at = datetime.now(UTC)
        if run.status == RunStatus.QUEUED:
            ensure_run_transition(RunStatus.QUEUED, RunStatus.RUNNING)
            run.status = RunStatus.RUNNING
            _add_event(
                session,
                run,
                task,
                "run.status_changed",
                {"from": previous_run_status, "to": RunStatus.RUNNING},
            )
        _add_event(
            session,
            run,
            task,
            "task.status_changed",
            {"from": TaskStatus.QUEUED, "to": TaskStatus.RUNNING},
        )
        session.commit()

    published_keys: list[str] = []
    try:
        with TemporaryDirectory(
            dir=settings.attempt_sandbox_root,
            prefix=f"{parsed_task_id}-attempt-{selected_number}-",
        ) as sandbox:
            with get_session_factory()() as session:
                task = session.get(Task, parsed_task_id)
                run = session.get(Run, task.run_id)
                configuration = dict(run.configuration)
            context = TaskContext(
                configuration=configuration,
                sandbox=Path(sandbox),
                settings=settings,
                task_id=task_id,
                attempt_number=selected_number,
            )
            prepared = stage_runner.prepare(context)
            result = stage_runner.execute(prepared, context)
            validation = stage_runner.validate(result)
            if not validation.valid:
                raise DomainError(
                    "dataset.validation_failed",
                    validation.reason or "The dataset output failed validation",
                )
            specs = stage_runner.publish(result, context)

            dataset_id = uuid.uuid4()
            stored_outputs: list[tuple[uuid.UUID, object, object, str]] = []
            for spec in specs:
                artifact_id = uuid.uuid4()
                key = (
                    f"projects/{run.project_id}/datasets/{dataset_id}/"
                    f"{artifact_id}/{spec.filename}"
                )
                stored = store.put_file(spec.path, key=key, content_type=spec.content_type)
                published_keys.append(key)
                stored_outputs.append((artifact_id, spec, stored, key))

            with get_session_factory()() as session:
                task = session.scalar(
                    select(Task).where(Task.id == parsed_task_id).with_for_update()
                )
                run = session.scalar(select(Run).where(Run.id == task.run_id).with_for_update())
                attempt = session.scalar(
                    select(Attempt)
                    .where(Attempt.task_id == task.id, Attempt.number == selected_number)
                    .with_for_update()
                )
                if task.status == TaskStatus.CANCEL_REQUESTED:
                    _finish_cancelled(session, run=run, task=task, attempt=attempt)
                    session.commit()
                    for key in published_keys:
                        store.delete(key)
                    _cleanup_stage_inputs(
                        stage_runner,
                        configuration=dict(run.configuration),
                        settings=settings,
                    )
                    return {"status": "cancelled"}
                if task.status != TaskStatus.RUNNING or attempt.status != AttemptStatus.RUNNING:
                    for key in published_keys:
                        store.delete(key)
                    return {"status": "superseded", "task_id": task_id}

                artifact_by_kind: dict[str, uuid.UUID] = {}
                for artifact_id, spec, stored, key in stored_outputs:
                    artifact_by_kind[spec.kind] = artifact_id
                    session.add(
                        Artifact(
                            id=artifact_id,
                            project_id=run.project_id,
                            attempt_id=attempt.id,
                            kind=spec.kind,
                            key=key,
                            filename=spec.filename,
                            content_type=spec.content_type,
                            size_bytes=stored.size_bytes,
                            sha256=stored.sha256,
                            schema_version=spec.schema_version,
                        )
                    )
                    _add_event(
                        session,
                        run,
                        task,
                        "artifact.published",
                        {
                            "artifact_id": str(artifact_id),
                            "kind": spec.kind,
                            "sha256": stored.sha256,
                        },
                    )

                if stage_runner.register_dataset:
                    session.add(
                        Dataset(
                            id=dataset_id,
                            project_id=run.project_id,
                            source_run_id=run.id,
                            artifact_id=artifact_by_kind[stage_runner.data_artifact_kind],
                            provenance_artifact_id=artifact_by_kind[
                                stage_runner.provenance_artifact_kind
                            ],
                            kind=stage_runner.dataset_kind,
                            label=str(run.configuration["dataset_label"]),
                            row_count=result.row_count,
                            provenance=result.provenance,
                        )
                    )
                now = datetime.now(UTC)
                ensure_task_transition(TaskStatus.RUNNING, TaskStatus.SUCCEEDED)
                ensure_run_transition(RunStatus.RUNNING, RunStatus.SUCCEEDED)
                task.status = TaskStatus.SUCCEEDED
                task.scientific_status = stage_runner.scientific_status
                task.finished_at = now
                attempt.status = AttemptStatus.SUCCEEDED
                attempt.finished_at = now
                run.status = RunStatus.SUCCEEDED
                run.finished_at = now
                if stage_runner.register_dataset:
                    _add_event(
                        session,
                        run,
                        task,
                        "dataset.registered",
                        {"dataset_id": str(dataset_id), "row_count": result.row_count},
                    )
                else:
                    _add_event(
                        session,
                        run,
                        task,
                        "stage.output_registered",
                        {"row_count": result.row_count},
                    )
                _add_event(
                    session,
                    run,
                    task,
                    "task.status_changed",
                    {"from": TaskStatus.RUNNING, "to": TaskStatus.SUCCEEDED},
                )
                _add_event(
                    session,
                    run,
                    task,
                    "run.status_changed",
                    {"from": RunStatus.RUNNING, "to": RunStatus.SUCCEEDED},
                )
                session.commit()
                try:
                    stage_runner.cleanup(context)
                except Exception:
                    logger.warning("Dataset quarantine cleanup failed", exc_info=True)
                response = {"status": "succeeded", "row_count": result.row_count}
                if stage_runner.register_dataset:
                    response["dataset_id"] = str(dataset_id)
                return response
    except Exception as error:
        for key in published_keys:
            store.delete(key)
        if isinstance(error, DomainError):
            error_code = error.code
            error_message = error.message
        else:
            logger.exception("Dataset task failed: %s", type(error).__name__)
            error_code = "dataset.execution_failed"
            error_message = stage_runner.execution_error_message
        with get_session_factory()() as session:
            task = session.scalar(select(Task).where(Task.id == parsed_task_id).with_for_update())
            run = session.scalar(select(Run).where(Run.id == task.run_id).with_for_update())
            attempt = session.scalar(
                select(Attempt)
                .where(Attempt.task_id == task.id, Attempt.number == selected_number)
                .with_for_update()
            )
            if task.status == TaskStatus.CANCEL_REQUESTED:
                configuration = dict(run.configuration)
                _finish_cancelled(session, run=run, task=task, attempt=attempt)
                session.commit()
                _cleanup_stage_inputs(stage_runner, configuration=configuration, settings=settings)
                return {"status": "cancelled"}
            if task.status != TaskStatus.RUNNING or attempt.status != AttemptStatus.RUNNING:
                return {"status": "superseded", "task_id": task_id}
            now = datetime.now(UTC)
            ensure_task_transition(TaskStatus.RUNNING, TaskStatus.FAILED)
            ensure_run_transition(RunStatus(run.status), RunStatus.FAILED)
            task.status = TaskStatus.FAILED
            task.finished_at = now
            attempt.status = AttemptStatus.FAILED
            attempt.error_code = error_code
            attempt.error_message = error_message
            attempt.finished_at = now
            run.status = RunStatus.FAILED
            run.finished_at = now
            _add_event(
                session,
                run,
                task,
                "task.status_changed",
                {"from": TaskStatus.RUNNING, "to": TaskStatus.FAILED, "error_code": error_code},
            )
            _add_event(
                session,
                run,
                task,
                "run.status_changed",
                {"from": RunStatus.RUNNING, "to": RunStatus.FAILED},
            )
            session.commit()
        return {"status": "failed", "task_id": task_id, "error_code": error_code}


@celery_app.task(name="ssscreen_web.dataset.mp_offline", bind=True, acks_late=True)
def prepare_mp_offline_dataset(
    self, task_id: str, attempt_number: int | None = None
) -> dict[str, object]:
    return prepare_dataset(self, task_id, attempt_number, runner)


def recover_stale_dataset_tasks(
    *, task_type: str, timeout_seconds: float, error_message: str
) -> int:
    settings = get_settings()
    del settings
    cutoff = datetime.now(UTC) - timedelta(seconds=timeout_seconds)
    recovered = 0
    with get_session_factory()() as session:
        tasks = list(
            session.scalars(
                select(Task)
                .where(
                    Task.task_type == task_type,
                    Task.status == TaskStatus.RUNNING,
                    Task.started_at < cutoff,
                )
                .with_for_update(skip_locked=True)
            ).all()
        )
        for task in tasks:
            run = session.scalar(select(Run).where(Run.id == task.run_id).with_for_update())
            attempt = session.scalar(
                select(Attempt)
                .where(Attempt.task_id == task.id)
                .order_by(Attempt.number.desc())
                .limit(1)
                .with_for_update()
            )
            if attempt is None or attempt.status != AttemptStatus.RUNNING:
                continue
            now = datetime.now(UTC)
            ensure_task_transition(TaskStatus.RUNNING, TaskStatus.FAILED)
            ensure_run_transition(RunStatus(run.status), RunStatus.FAILED)
            task.status = TaskStatus.FAILED
            task.finished_at = now
            attempt.status = AttemptStatus.FAILED
            attempt.error_code = "worker.lost"
            attempt.error_message = error_message
            attempt.finished_at = now
            run.status = RunStatus.FAILED
            run.finished_at = now
            _add_event(
                session,
                run,
                task,
                "task.status_changed",
                {
                    "from": TaskStatus.RUNNING,
                    "to": TaskStatus.FAILED,
                    "error_code": "worker.lost",
                },
            )
            _add_event(
                session,
                run,
                task,
                "run.status_changed",
                {"from": RunStatus.RUNNING, "to": RunStatus.FAILED},
            )
            recovered += 1
        session.commit()
    return recovered


def recover_stale_mp_dataset_tasks() -> int:
    return recover_stale_dataset_tasks(
        task_type=runner.task_type,
        timeout_seconds=get_settings().mp_dataset_task_stale_seconds,
        error_message="The Stage 1 dataset worker stopped before reporting a terminal state",
    )
