from __future__ import annotations

import json
import socket
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import ssscreen
from celery.utils.log import get_task_logger
from sqlalchemy import select

from ssscreen_web.domain.enums import AttemptStatus, RunStatus, TaskStatus
from ssscreen_web.domain.transitions import ensure_run_transition, ensure_task_transition
from ssscreen_web.infrastructure.artifacts import FileSystemArtifactStore
from ssscreen_web.infrastructure.database import get_session_factory
from ssscreen_web.infrastructure.models import Artifact, Attempt, Event, Run, Task
from ssscreen_web.settings import get_settings
from ssscreen_web.workers.celery_app import celery_app

logger = get_task_logger(__name__)


def _add_event(session, run: Run, task: Task, kind: str, payload: dict[str, object]) -> None:
    session.add(
        Event(
            project_id=run.project_id,
            run_id=run.id,
            task_id=task.id,
            kind=kind,
            payload=payload,
        )
    )


def _finish_cancelled(session, *, run: Run, task: Task, attempt: Attempt) -> None:
    now = datetime.now(UTC)
    current_task_status = TaskStatus(task.status)
    ensure_task_transition(current_task_status, TaskStatus.CANCELLED)
    current_run_status = RunStatus(run.status)
    ensure_run_transition(current_run_status, RunStatus.CANCELLED)
    task.status = TaskStatus.CANCELLED
    task.finished_at = now
    attempt.status = AttemptStatus.CANCELLED
    attempt.finished_at = now
    run.status = RunStatus.CANCELLED
    run.finished_at = now
    _add_event(
        session,
        run,
        task,
        "task.status_changed",
        {"from": current_task_status, "to": TaskStatus.CANCELLED},
    )
    _add_event(
        session,
        run,
        task,
        "run.status_changed",
        {"from": current_run_status, "to": RunStatus.CANCELLED},
    )


@celery_app.task(name="ssscreen_web.example.generate_json", bind=True, acks_late=True)
def generate_json(self, task_id: str, attempt_number: int | None = None) -> dict[str, object]:
    parsed_task_id = uuid.UUID(task_id)
    settings = get_settings()
    store = FileSystemArtifactStore(settings.artifact_root)
    store.ensure_ready()
    FileSystemArtifactStore(settings.attempt_sandbox_root).ensure_ready()
    with get_session_factory()() as session:
        task = session.scalar(select(Task).where(Task.id == parsed_task_id).with_for_update())
        if task is None:
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
            return {
                "status": "superseded",
                "task_id": task_id,
                "attempt_number": selected_number,
            }
        if task.status in {TaskStatus.SUCCEEDED, TaskStatus.CANCELLED} or attempt.status in {
            AttemptStatus.SUCCEEDED,
            AttemptStatus.FAILED,
            AttemptStatus.CANCELLED,
        }:
            return {"status": "duplicate", "task_id": task_id}
        if task.status == TaskStatus.RUNNING and attempt.status == AttemptStatus.RUNNING:
            return {"status": "active", "task_id": task_id}
        if task.status == TaskStatus.CANCEL_REQUESTED:
            _finish_cancelled(session, run=run, task=task, attempt=attempt)
            session.commit()
            return {"status": "cancelled"}
        if task.status != TaskStatus.QUEUED or attempt.status != AttemptStatus.QUEUED:
            return {"status": "ignored", "task_id": task_id}
        ensure_task_transition(TaskStatus(task.status), TaskStatus.RUNNING)
        previous_run_status = RunStatus(run.status)
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(UTC)
        attempt.status = AttemptStatus.RUNNING
        attempt.worker_id = f"{socket.gethostname()}:{self.request.id or 'direct'}"
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

    published_key: str | None = None
    try:
        with get_session_factory()() as session:
            task = session.scalar(select(Task).where(Task.id == parsed_task_id).with_for_update())
            run = session.scalar(select(Run).where(Run.id == task.run_id).with_for_update())
            attempt = session.scalar(
                select(Attempt)
                .where(Attempt.task_id == task.id, Attempt.number == selected_number)
                .with_for_update()
            )
            if task.status == TaskStatus.CANCEL_REQUESTED:
                _finish_cancelled(session, run=run, task=task, attempt=attempt)
                session.commit()
                return {"status": "cancelled"}
            if run.configuration.get("simulate_failure") and attempt.number == 1:
                raise RuntimeError("Requested deterministic demo failure")
            payload = {
                "schema_version": 1,
                "run_id": str(run.id),
                "task_id": str(task.id),
                "message": run.configuration["message"],
                "ssscreen_version": ssscreen.__version__,
            }
            content = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode()
            artifact_id = uuid.uuid4()
            key = (
                f"projects/{run.project_id}/runs/{run.id}/tasks/{task.id}/"
                f"attempts/{attempt.number}/outputs/{artifact_id}.json"
            )
            with TemporaryDirectory(
                dir=settings.attempt_sandbox_root,
                prefix=f"{task.id}-attempt-{attempt.number}-",
            ) as sandbox:
                output = Path(sandbox) / "control-plane-demo.json"
                output.write_bytes(content)
                stored = store.put_file(output, key=key, content_type="application/json")
            published_key = key
            session.add(
                Artifact(
                    id=artifact_id,
                    project_id=run.project_id,
                    attempt_id=attempt.id,
                    kind="control-plane-demo-json",
                    key=key,
                    filename="control-plane-demo.json",
                    content_type="application/json",
                    size_bytes=stored.size_bytes,
                    sha256=stored.sha256,
                    schema_version="1",
                )
            )
            now = datetime.now(UTC)
            ensure_task_transition(TaskStatus.RUNNING, TaskStatus.SUCCEEDED)
            ensure_run_transition(RunStatus.RUNNING, RunStatus.SUCCEEDED)
            task.status = TaskStatus.SUCCEEDED
            task.scientific_status = "not_applicable"
            task.finished_at = now
            attempt.status = AttemptStatus.SUCCEEDED
            attempt.finished_at = now
            run.status = RunStatus.SUCCEEDED
            run.finished_at = now
            _add_event(
                session,
                run,
                task,
                "artifact.published",
                {"artifact_id": str(artifact_id), "sha256": stored.sha256},
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
            return {"status": "succeeded", "artifact_id": str(artifact_id)}
    except Exception as error:
        logger.warning("Example task failed: %s", type(error).__name__)
        if published_key is not None:
            store.delete(published_key)
        with get_session_factory()() as session:
            task = session.scalar(select(Task).where(Task.id == parsed_task_id).with_for_update())
            run = session.scalar(select(Run).where(Run.id == task.run_id).with_for_update())
            attempt = session.scalar(
                select(Attempt)
                .where(Attempt.task_id == task.id, Attempt.number == selected_number)
                .with_for_update()
            )
            if task.status == TaskStatus.CANCEL_REQUESTED:
                _finish_cancelled(session, run=run, task=task, attempt=attempt)
                session.commit()
                return {"status": "cancelled"}
            if task.status != TaskStatus.RUNNING or attempt.status != AttemptStatus.RUNNING:
                return {"status": "superseded", "task_id": task_id}
            now = datetime.now(UTC)
            ensure_task_transition(TaskStatus(task.status), TaskStatus.FAILED)
            ensure_run_transition(RunStatus(run.status), RunStatus.FAILED)
            task.status = TaskStatus.FAILED
            task.finished_at = now
            attempt.status = AttemptStatus.FAILED
            attempt.error_code = (
                "demo.requested_failure"
                if run.configuration.get("simulate_failure")
                else "worker.unexpected"
            )
            attempt.error_message = (
                "The deterministic demo task was configured to fail"
                if run.configuration.get("simulate_failure")
                else "The worker could not complete the task"
            )
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
                    "error_code": attempt.error_code,
                },
            )
            _add_event(
                session,
                run,
                task,
                "run.status_changed",
                {"from": RunStatus.RUNNING, "to": RunStatus.FAILED},
            )
            session.commit()
        return {"status": "failed", "task_id": task_id}


def recover_stale_demo_tasks() -> int:
    settings = get_settings()
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.demo_task_stale_seconds)
    recovered = 0
    with get_session_factory()() as session:
        tasks = list(
            session.scalars(
                select(Task)
                .where(
                    Task.task_type == "example.generate-json",
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
            attempt.error_message = "The demo worker stopped before reporting a terminal state"
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
