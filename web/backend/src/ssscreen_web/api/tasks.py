from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ssscreen_web.api.dependencies import get_current_user
from ssscreen_web.api.schemas import AttemptResponse, TaskDetail, TaskResponse
from ssscreen_web.application.runs import cancel_task, retry_task
from ssscreen_web.application.upload_lifecycle import cleanup_wbm_quarantine
from ssscreen_web.domain.errors import DomainError
from ssscreen_web.infrastructure.database import get_db
from ssscreen_web.infrastructure.models import Attempt, Run, Task, User
from ssscreen_web.infrastructure.repositories import require_project_role
from ssscreen_web.settings import Settings, get_settings
from ssscreen_web.workers.celery_app import dispatch_pending_outbox

router = APIRouter(prefix="/api/v1", tags=["tasks"])


def _get_authorized_task(
    session: Session, *, task_id: uuid.UUID, user: User, write: bool = False
) -> tuple[Task, Run]:
    task = session.get(Task, task_id)
    if task is None:
        raise DomainError("task.not_found", "Task was not found", status_code=404)
    run = session.get(Run, task.run_id)
    require_project_role(session, project_id=run.project_id, user_id=user.id, write=write)
    return task, run


@router.get("/runs/{run_id}/tasks", response_model=list[TaskResponse])
def list_for_run(
    run_id: uuid.UUID,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Task]:
    run = session.get(Run, run_id)
    if run is None:
        raise DomainError("run.not_found", "Run was not found", status_code=404)
    require_project_role(session, project_id=run.project_id, user_id=user.id)
    return list(
        session.scalars(select(Task).where(Task.run_id == run_id).order_by(Task.created_at)).all()
    )


@router.get("/tasks/{task_id}", response_model=TaskDetail)
def detail(
    task_id: uuid.UUID,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskDetail:
    task, _ = _get_authorized_task(session, task_id=task_id, user=user)
    attempts = list(
        session.scalars(
            select(Attempt).where(Attempt.task_id == task.id).order_by(Attempt.number)
        ).all()
    )
    return TaskDetail(
        **TaskResponse.model_validate(task).model_dump(),
        attempts=[AttemptResponse.model_validate(item) for item in attempts],
    )


@router.post("/tasks/{task_id}/actions/retry", response_model=AttemptResponse)
def retry(
    task_id: uuid.UUID,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Attempt:
    task, run = _get_authorized_task(session, task_id=task_id, user=user, write=True)
    attempt = retry_task(session, task=task, run=run, user=user)
    dispatch_pending_outbox()
    return attempt


@router.post("/tasks/{task_id}/actions/cancel", response_model=TaskResponse)
def cancel(
    task_id: uuid.UUID,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> Task:
    task, run = _get_authorized_task(session, task_id=task_id, user=user, write=True)
    cancelled = cancel_task(session, task=task, run=run, user=user)
    if cancelled.status == "CANCELLED":
        cleanup_wbm_quarantine(dict(run.configuration), settings=settings)
    return cancelled
