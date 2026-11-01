from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ssscreen_web.domain.enums import UserStatus
from ssscreen_web.domain.errors import DomainError
from ssscreen_web.infrastructure.database import get_db
from ssscreen_web.infrastructure.models import User
from ssscreen_web.settings import Settings, get_settings


@dataclass(frozen=True)
class CurrentUser:
    id: object
    subject: str
    display_name: str


def get_current_user(
    session: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> User:
    if not settings.dev_auth_enabled:
        raise DomainError(
            "auth.unavailable", "OIDC authentication is not configured", status_code=503
        )
    user = session.scalar(select(User).where(User.oidc_subject == settings.dev_user_subject))
    if user is None:
        user_id = session.scalar(
            insert(User)
            .values(
                oidc_subject=settings.dev_user_subject,
                display_name=settings.dev_user_display_name,
                status=UserStatus.ACTIVE,
            )
            .on_conflict_do_update(
                index_elements=[User.oidc_subject],
                set_={"display_name": settings.dev_user_display_name},
            )
            .returning(User.id)
        )
        session.commit()
        user = session.get(User, user_id)
    if user.status != UserStatus.ACTIVE:
        raise DomainError("auth.disabled", "The current account is disabled", status_code=403)
    return user
