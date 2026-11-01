from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ssscreen_web.application.pipelines import pipeline_spec, task_spec
from ssscreen_web.domain.enums import AttemptStatus, OutboxStatus, RunStatus, TaskStatus
from ssscreen_web.domain.errors import DomainError
from ssscreen_web.domain.transitions import ensure_run_transition, ensure_task_transition
from ssscreen_web.infrastructure.models import Attempt, Event, OutboxMessage, Run, Task, User


def _event(
    session: Session,
    *,
    run: Run,
    task: Task | None,
    kind: str,
    payload: dict[str, object],
    actor: User | None,
) -> None:
    session.add(
        Event(
            project_id=run.project_id,
            run_id=run.id,
            task_id=task.id if task else None,
            kind=kind,
            payload=payload,
            actor_id=actor.id if actor else None,
        )
    )


def create_run(
    session: Session, *, project_id: uuid.UUID, configuration: dict[str, object], user: User
) -> Run:
    spec = pipeline_spec(configuration.get("pipeline"))
    run = Run(
        project_id=project_id,
        pipeline_version=spec.version,
        configuration=configuration,
        status=RunStatus.DRAFT,
    )
    session.add(run)
    session.flush()
    _event(
        session,
        run=run,
        task=None,
        kind="run.created",
        payload={"status": run.status},
        actor=user,
    )
    session.commit()
    session.refresh(run)
    return run


def _latest_attempt(session: Session, task_id: uuid.UUID) -> Attempt | None:
    return session.scalar(
        select(Attempt)
        .where(Attempt.task_id == task_id)
        .order_by(Attempt.number.desc())
        .limit(1)
        .with_for_update()
    )


def _cancel_queued_attempt(session: Session, *, task: Task, now: datetime) -> None:
    attempt = _latest_attempt(session, task.id)
    if attempt is None or attempt.status != AttemptStatus.QUEUED:
        return
    attempt.status = AttemptStatus.CANCELLED
    attempt.finished_at = now
    session.execute(
        delete(OutboxMessage).where(
            OutboxMessage.deduplication_key == f"task:{task.id}:attempt:{attempt.number}",
            OutboxMessage.status.in_([OutboxStatus.PENDING, OutboxStatus.FAILED]),
        )
    )


def start_run(session: Session, *, run: Run, user: User) -> Task:
    session.refresh(run, with_for_update=True)
    existing = session.scalar(select(Task).where(Task.run_id == run.id))
    if existing is not None:
        raise DomainError("run.already_started", "Run already has a task", status_code=409)
    ensure_run_transition(RunStatus(run.status), RunStatus.QUEUED)
    run.status = RunStatus.QUEUED
    run.started_at = datetime.now(UTC)
    spec = pipeline_spec(run.configuration.get("pipeline"))
    task = Task(
        run_id=run.id,
        stage=spec.stage,
        task_type=spec.task_type,
        status=TaskStatus.QUEUED,
    )
    session.add(task)
    session.flush()
    settings_hash = hashlib.sha256(
        json.dumps(run.configuration, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    attempt = Attempt(
        task_id=task.id,
        number=1,
        status=AttemptStatus.QUEUED,
        settings_hash=settings_hash,
    )
    session.add(attempt)
    session.add(
        OutboxMessage(
            topic=spec.topic,
            payload={"task_id": str(task.id), "attempt_number": 1},
            deduplication_key=f"task:{task.id}:attempt:1",
            status=OutboxStatus.PENDING,
        )
    )
    _event(
        session,
        run=run,
        task=None,
        kind="run.status_changed",
        payload={"from": RunStatus.DRAFT, "to": RunStatus.QUEUED},
        actor=user,
    )
    _event(
        session,
        run=run,
        task=task,
        kind="task.queued",
        payload={"status": TaskStatus.QUEUED, "attempt": 1},
        actor=user,
    )
    session.commit()
    session.refresh(task)
    return task


def cancel_run(session: Session, *, run: Run, user: User) -> Run:
    session.refresh(run, with_for_update=True)
    tasks = list(session.scalars(select(Task).where(Task.run_id == run.id).with_for_update()).all())
    previous_run_status = RunStatus(run.status)
    now = datetime.now(UTC)
    if run.status == RunStatus.DRAFT:
        ensure_run_transition(RunStatus.DRAFT, RunStatus.CANCELLED)
        run.status = RunStatus.CANCELLED
        run.finished_at = now
    elif run.status in {RunStatus.QUEUED, RunStatus.RUNNING}:
        for task in tasks:
            previous_task_status = TaskStatus(task.status)
            if task.status in {TaskStatus.PENDING, TaskStatus.READY, TaskStatus.QUEUED}:
                ensure_task_transition(previous_task_status, TaskStatus.CANCELLED)
                task.status = TaskStatus.CANCELLED
                task.finished_at = now
                _cancel_queued_attempt(session, task=task, now=now)
            elif task.status == TaskStatus.RUNNING:
                ensure_task_transition(TaskStatus.RUNNING, TaskStatus.CANCEL_REQUESTED)
                task.status = TaskStatus.CANCEL_REQUESTED
            else:
                continue
            _event(
                session,
                run=run,
                task=task,
                kind="task.status_changed",
                payload={"from": previous_task_status, "to": task.status},
                actor=user,
            )
        if all(task.status == TaskStatus.CANCELLED for task in tasks):
            ensure_run_transition(previous_run_status, RunStatus.CANCELLED)
            run.status = RunStatus.CANCELLED
            run.finished_at = now
    else:
        raise DomainError(
            "run.invalid_transition", f"Run cannot be cancelled from {run.status}", status_code=409
        )
    _event(
        session,
        run=run,
        task=None,
        kind="run.cancel_requested",
        payload={"status": run.status},
        actor=user,
    )
    if run.status != previous_run_status:
        _event(
            session,
            run=run,
            task=None,
            kind="run.status_changed",
            payload={"from": previous_run_status, "to": run.status},
            actor=user,
        )
    session.commit()
    session.refresh(run)
    return run


def cancel_task(session: Session, *, task: Task, run: Run, user: User) -> Task:
    session.refresh(task, with_for_update=True)
    session.refresh(run, with_for_update=True)
    current = TaskStatus(task.status)
    target = TaskStatus.CANCEL_REQUESTED if current == TaskStatus.RUNNING else TaskStatus.CANCELLED
    ensure_task_transition(current, target)
    task.status = target
    now = datetime.now(UTC)
    if target == TaskStatus.CANCELLED:
        task.finished_at = now
        _cancel_queued_attempt(session, task=task, now=now)
    _event(
        session,
        run=run,
        task=task,
        kind="task.cancel_requested",
        payload={"status": target},
        actor=user,
    )
    _event(
        session,
        run=run,
        task=task,
        kind="task.status_changed",
        payload={"from": current, "to": target},
        actor=user,
    )
    task_states = list(session.scalars(select(Task.status).where(Task.run_id == run.id)).all())
    if target == TaskStatus.CANCELLED and all(
        state == TaskStatus.CANCELLED for state in task_states
    ):
        previous_run_status = RunStatus(run.status)
        ensure_run_transition(previous_run_status, RunStatus.CANCELLED)
        run.status = RunStatus.CANCELLED
        run.finished_at = now
        _event(
            session,
            run=run,
            task=None,
            kind="run.status_changed",
            payload={"from": previous_run_status, "to": RunStatus.CANCELLED},
            actor=user,
        )
    session.commit()
    session.refresh(task)
    return task


def retry_task(session: Session, *, task: Task, run: Run, user: User) -> Attempt:
    session.refresh(task, with_for_update=True)
    session.refresh(run, with_for_update=True)
    ensure_task_transition(TaskStatus(task.status), TaskStatus.READY)
    task.status = TaskStatus.READY
    number = (
        session.scalar(select(func.max(Attempt.number)).where(Attempt.task_id == task.id)) or 0
    ) + 1
    previous = session.scalar(
        select(Attempt).where(Attempt.task_id == task.id).order_by(Attempt.number.desc()).limit(1)
    )
    attempt = Attempt(
        task_id=task.id,
        number=number,
        status=AttemptStatus.QUEUED,
        settings_hash=previous.settings_hash if previous else "0" * 64,
    )
    session.add(attempt)
    ensure_task_transition(TaskStatus.READY, TaskStatus.QUEUED)
    task.status = TaskStatus.QUEUED
    if run.status == RunStatus.FAILED:
        ensure_run_transition(RunStatus.FAILED, RunStatus.QUEUED)
        run.status = RunStatus.QUEUED
        run.finished_at = None
    spec = task_spec(task.task_type)
    session.add(
        OutboxMessage(
            topic=spec.topic,
            payload={"task_id": str(task.id), "attempt_number": number},
            deduplication_key=f"task:{task.id}:attempt:{number}",
            status=OutboxStatus.PENDING,
        )
    )
    _event(
        session, run=run, task=task, kind="task.retried", payload={"attempt": number}, actor=user
    )
    _event(
        session,
        run=run,
        task=task,
        kind="task.status_changed",
        payload={"from": TaskStatus.FAILED, "to": TaskStatus.READY},
        actor=user,
    )
    _event(
        session,
        run=run,
        task=task,
        kind="task.status_changed",
        payload={"from": TaskStatus.READY, "to": TaskStatus.QUEUED},
        actor=user,
    )
    session.commit()
    session.refresh(attempt)
    return attempt
