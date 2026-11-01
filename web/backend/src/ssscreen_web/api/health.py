from __future__ import annotations

from fastapi import APIRouter, Depends
from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from ssscreen_web.application.scientific_runtime import require_scientific_runtime
from ssscreen_web.infrastructure.artifacts import FileSystemArtifactStore
from ssscreen_web.infrastructure.database import get_db
from ssscreen_web.settings import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok", "service": "ssscreen-web-api"}


@router.get("/health/ready")
def ready(
    session: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> dict[str, object]:
    checks: dict[str, str] = {}
    session.execute(text("SELECT 1"))
    checks["database"] = "ok"
    client = Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
    try:
        client.ping()
        checks["redis"] = "ok"
    finally:
        client.close()
    storage_roots = {
        "artifact_store": settings.artifact_root,
        "attempt_sandboxes": settings.attempt_sandbox_root,
        "uploads_quarantine": settings.uploads_quarantine_root,
    }
    for name, root in storage_roots.items():
        FileSystemArtifactStore(root).ensure_ready()
        checks[name] = "ok"
    require_scientific_runtime(settings)
    checks["scientific_core"] = "ok"
    return {"status": "ready", "checks": checks}
