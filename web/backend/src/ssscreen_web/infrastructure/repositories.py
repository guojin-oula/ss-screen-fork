from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ssscreen_web.domain.enums import ProjectRole
from ssscreen_web.domain.errors import DomainError
from ssscreen_web.infrastructure.models import ProjectMember

WRITE_ROLES = {ProjectRole.OWNER, ProjectRole.EDITOR}


def require_project_role(
    session: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    write: bool = False,
) -> ProjectRole:
    role = session.scalar(
        select(ProjectMember.role).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
        )
    )
    if role is None:
        raise DomainError("project.not_found", "Project was not found", status_code=404)
    parsed = ProjectRole(role)
    if write and parsed not in WRITE_ROLES:
        raise DomainError("project.forbidden", "This project role is read-only", status_code=403)
    return parsed
