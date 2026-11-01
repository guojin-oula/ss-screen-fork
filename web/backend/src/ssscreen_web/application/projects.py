from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ssscreen_web.domain.enums import ProjectRole
from ssscreen_web.infrastructure.models import Event, Project, ProjectMember, Run, User


def create_project(session: Session, *, user: User, name: str, description: str) -> Project:
    project = Project(name=name, description=description, owner_id=user.id)
    session.add(project)
    session.flush()
    session.add(ProjectMember(project_id=project.id, user_id=user.id, role=ProjectRole.OWNER))
    session.add(
        Event(
            project_id=project.id,
            kind="project.created",
            payload={"name": project.name},
            actor_id=user.id,
        )
    )
    session.commit()
    session.refresh(project)
    return project


def list_projects(
    session: Session, *, user: User
) -> list[tuple[Project, str, str, uuid.UUID | None, str | None]]:
    owner_name = (
        select(User.display_name)
        .where(User.id == Project.owner_id)
        .correlate(Project)
        .scalar_subquery()
    )
    latest_run_id = (
        select(Run.id)
        .where(Run.project_id == Project.id)
        .order_by(Run.created_at.desc())
        .limit(1)
        .correlate(Project)
        .scalar_subquery()
    )
    latest_run_status = (
        select(Run.status)
        .where(Run.project_id == Project.id)
        .order_by(Run.created_at.desc())
        .limit(1)
        .correlate(Project)
        .scalar_subquery()
    )
    rows = session.execute(
        select(Project, ProjectMember.role, owner_name, latest_run_id, latest_run_status)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == user.id)
        .order_by(Project.updated_at.desc())
    ).all()
    return [(row[0], row[1], row[2], row[3], row[4]) for row in rows]
