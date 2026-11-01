from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ssscreen_web.api.dependencies import get_current_user
from ssscreen_web.domain.errors import DomainError
from ssscreen_web.infrastructure.database import get_db, get_session_factory
from ssscreen_web.infrastructure.models import Event, Run, User
from ssscreen_web.infrastructure.repositories import require_project_role
from ssscreen_web.settings import Settings, get_settings

router = APIRouter(prefix="/api/v1", tags=["events"])


async def _stream_events(
    request: Request, run_id: uuid.UUID, cursor: int, settings: Settings
) -> AsyncIterator[str]:
    heartbeat_elapsed = 0.0
    while not await request.is_disconnected():
        with get_session_factory()() as session:
            events = list(
                session.scalars(
                    select(Event)
                    .where(Event.run_id == run_id, Event.id > cursor)
                    .order_by(Event.id)
                    .limit(100)
                ).all()
            )
        if events:
            for event in events:
                cursor = event.id
                data = {
                    "id": event.id,
                    "kind": event.kind,
                    "run_id": str(event.run_id) if event.run_id else None,
                    "task_id": str(event.task_id) if event.task_id else None,
                    "payload": event.payload,
                    "created_at": event.created_at.isoformat(),
                }
                yield f"id: {event.id}\nevent: {event.kind}\ndata: {json.dumps(data)}\n\n"
            heartbeat_elapsed = 0.0
        else:
            await asyncio.sleep(settings.sse_poll_seconds)
            heartbeat_elapsed += settings.sse_poll_seconds
            if heartbeat_elapsed >= settings.sse_heartbeat_seconds:
                yield ": heartbeat\n\n"
                heartbeat_elapsed = 0.0


@router.get("/runs/{run_id}/events")
def events(
    run_id: uuid.UUID,
    request: Request,
    last_event_id: int | None = Header(default=None, alias="Last-Event-ID"),
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    run = session.get(Run, run_id)
    if run is None:
        raise DomainError("run.not_found", "Run was not found", status_code=404)
    require_project_role(session, project_id=run.project_id, user_id=user.id)
    return StreamingResponse(
        _stream_events(request, run_id, max(last_event_id or 0, 0), settings),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
