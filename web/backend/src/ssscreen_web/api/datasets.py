from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ssscreen_web.api.dependencies import get_current_user
from ssscreen_web.api.schemas import DatasetResponse
from ssscreen_web.domain.errors import DomainError
from ssscreen_web.infrastructure.database import get_db
from ssscreen_web.infrastructure.models import Dataset, User
from ssscreen_web.infrastructure.repositories import require_project_role

router = APIRouter(prefix="/api/v1", tags=["datasets"])


@router.get("/projects/{project_id}/datasets", response_model=list[DatasetResponse])
def list_for_project(
    project_id: uuid.UUID,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Dataset]:
    require_project_role(session, project_id=project_id, user_id=user.id)
    return list(
        session.scalars(
            select(Dataset)
            .where(Dataset.project_id == project_id)
            .order_by(Dataset.created_at.desc())
        ).all()
    )


@router.get("/datasets/{dataset_id}", response_model=DatasetResponse)
def detail(
    dataset_id: uuid.UUID,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dataset:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise DomainError("dataset.not_found", "Dataset was not found", status_code=404)
    require_project_role(session, project_id=dataset.project_id, user_id=user.id)
    return dataset
