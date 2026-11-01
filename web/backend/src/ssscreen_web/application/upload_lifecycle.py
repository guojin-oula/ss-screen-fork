from __future__ import annotations

import logging

from ssscreen_web.domain.errors import DomainError
from ssscreen_web.infrastructure.artifacts import FileSystemArtifactStore
from ssscreen_web.settings import Settings

logger = logging.getLogger(__name__)


def wbm_quarantine_keys(configuration: dict[str, object]) -> tuple[str, ...]:
    """Return validated logical keys only for the WBM upload pipeline."""
    if configuration.get("pipeline") != "stage-1-wbm-upload":
        return ()
    upload = configuration.get("upload")
    if not isinstance(upload, dict):
        return ()
    keys: list[str] = []
    for role in ("structures", "summary"):
        metadata = upload.get(role)
        if isinstance(metadata, dict) and isinstance(metadata.get("key"), str):
            keys.append(metadata["key"])
    return tuple(keys)


def cleanup_wbm_quarantine(configuration: dict[str, object], *, settings: Settings) -> int:
    """Best-effort removal after a committed terminal state."""
    store = FileSystemArtifactStore(settings.uploads_quarantine_root)
    deleted = 0
    for key in wbm_quarantine_keys(configuration):
        try:
            store.delete(key)
        except (DomainError, OSError):
            logger.warning("Could not remove WBM quarantine object", exc_info=True)
        else:
            deleted += 1
    return deleted
