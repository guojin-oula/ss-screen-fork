from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ssscreen_web.api.dependencies import get_current_user
from ssscreen_web.api.schemas import ProjectCreate, ProjectResponse
from ssscreen_web.application.projects import create_project, list_projects
from ssscreen_web.infrastructure.database import get_db
from ssscreen_web.infrastructure.models import Project, Run, User
from ssscreen_web.infrastructure.repositories import require_project_role

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def _response(
    project: Project,
    role: str | None = None,
    owner_display_name: str | None = None,
    latest_run_id: uuid.UUID | None = None,
    latest_run_status: str | None = None,
) -> ProjectResponse:
    return ProjectResponse.model_validate(project).model_copy(
        update={
            "role": role,
            "owner_display_name": owner_display_name,
            "latest_run_id": latest_run_id,
            "latest_run_status": latest_run_status,
        }
    )


@router.get("", response_model=list[ProjectResponse])
def projects(
    session: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[ProjectResponse]:
    return [
        _response(project, role, owner_name, latest_run_id, latest_run_status)
        for project, role, owner_name, latest_run_id, latest_run_status in list_projects(
            session, user=user
        )
    ]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create(
    body: ProjectCreate,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectResponse:
    project = create_project(session, user=user, name=body.name, description=body.description)
    return _response(project, "owner", user.display_name)


@router.get("/{project_id}", response_model=ProjectResponse)
def detail(
    project_id: uuid.UUID,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectResponse:
    role = require_project_role(session, project_id=project_id, user_id=user.id)
    project = session.get(Project, project_id)
    owner = session.get(User, project.owner_id)
    latest_run = session.scalar(
        select(Run).where(Run.project_id == project.id).order_by(Run.created_at.desc()).limit(1)
    )
    return _response(
        project,
        role,
        owner.display_name,
        latest_run.id if latest_run else None,
        latest_run.status if latest_run else None,
    )
