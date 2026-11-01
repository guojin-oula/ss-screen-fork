from __future__ import annotations

import csv
import io
import json
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ssscreen_web.api.dependencies import get_current_user
from ssscreen_web.api.schemas import (
    ArtifactResponse,
    CompositionCandidateResponse,
    CompositionPreviewResponse,
    CondensationFailureResponse,
    CondensationPreviewResponse,
)
from ssscreen_web.domain.errors import DomainError
from ssscreen_web.infrastructure.artifacts import FileSystemArtifactStore
from ssscreen_web.infrastructure.database import get_db
from ssscreen_web.infrastructure.models import Artifact, Event, Run, Task, User
from ssscreen_web.infrastructure.repositories import require_project_role
from ssscreen_web.settings import Settings, get_settings

router = APIRouter(prefix="/api/v1", tags=["artifacts"])


def _authorized_artifact(session: Session, *, artifact_id: uuid.UUID, user: User) -> Artifact:
    artifact = session.get(Artifact, artifact_id)
    if artifact is None:
        raise DomainError("artifact.not_found", "Artifact was not found", status_code=404)
    require_project_role(session, project_id=artifact.project_id, user_id=user.id)
    return artifact


def _artifacts_for_run(session: Session, run_id: uuid.UUID) -> list[Artifact]:
    from ssscreen_web.infrastructure.models import Attempt

    return list(
        session.scalars(
            select(Artifact)
            .join(Attempt, Artifact.attempt_id == Attempt.id)
            .join(Task, Attempt.task_id == Task.id)
            .where(Task.run_id == run_id)
            .order_by(Artifact.created_at.desc())
        ).all()
    )


def _composition_artifacts(artifacts: list[Artifact]) -> tuple[Artifact, Artifact]:
    candidates = next(
        (artifact for artifact in artifacts if artifact.kind == "composition-candidates"), None
    )
    if candidates is None:
        raise DomainError(
            "composition.preview_unavailable",
            "Composition candidates are not available yet",
            status_code=404,
        )
    provenance = next(
        (
            artifact
            for artifact in artifacts
            if artifact.kind == "composition-provenance"
            and artifact.attempt_id == candidates.attempt_id
        ),
        None,
    )
    if provenance is None:
        raise DomainError(
            "composition.preview_incomplete",
            "Composition preview provenance is unavailable",
            status_code=409,
        )
    return candidates, provenance


@router.get("/runs/{run_id}/artifacts", response_model=list[ArtifactResponse])
def list_for_run(
    run_id: uuid.UUID,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Artifact]:
    run = session.get(Run, run_id)
    if run is None:
        raise DomainError("run.not_found", "Run was not found", status_code=404)
    require_project_role(session, project_id=run.project_id, user_id=user.id)
    return _artifacts_for_run(session, run_id)


@router.get("/runs/{run_id}/composition-preview", response_model=CompositionPreviewResponse)
def composition_preview(
    run_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CompositionPreviewResponse:
    run = session.get(Run, run_id)
    if run is None:
        raise DomainError("run.not_found", "Run was not found", status_code=404)
    require_project_role(session, project_id=run.project_id, user_id=user.id)
    if run.pipeline_version != "stage-1a-composition-v1":
        raise DomainError(
            "composition.preview_unsupported",
            "This Run does not produce composition candidates",
        )

    candidates_artifact, provenance_artifact = _composition_artifacts(
        _artifacts_for_run(session, run_id)
    )
    store = FileSystemArtifactStore(settings.artifact_root)
    try:
        with store.open_read(provenance_artifact.key) as handle:
            provenance = json.load(handle)
        rows: list[CompositionCandidateResponse] = []
        with store.open_read(candidates_artifact.key) as binary_handle:
            with io.TextIOWrapper(binary_handle, encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    rows.append(CompositionCandidateResponse.model_validate(row))
                    if len(rows) >= limit:
                        break
        total_rows = int(provenance["row_count"])
        summary = provenance.get("summary", {})
        if total_rows < len(rows) or not isinstance(summary, dict):
            raise ValueError("invalid composition provenance")
    except (KeyError, TypeError, ValueError, csv.Error, UnicodeError) as error:
        raise DomainError(
            "composition.preview_invalid",
            "The composition preview artifact is invalid",
            status_code=409,
        ) from error

    return CompositionPreviewResponse(
        artifact_id=candidates_artifact.id,
        total_rows=total_rows,
        limit=limit,
        summary=summary,
        candidates=rows,
    )


@router.get("/runs/{run_id}/condensation-preview", response_model=CondensationPreviewResponse)
def condensation_preview(
    run_id: uuid.UUID,
    failure_limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CondensationPreviewResponse:
    run = session.get(Run, run_id)
    if run is None:
        raise DomainError("run.not_found", "Run was not found", status_code=404)
    require_project_role(session, project_id=run.project_id, user_id=user.id)
    if run.pipeline_version != "stage-2-condensation-v1":
        raise DomainError(
            "condensation.preview_unsupported",
            "This Run does not produce condensed structures",
        )

    total = int(run.configuration.get("candidate_count", 0))
    progress: dict[str, object] = {
        "total": total,
        "completed": 0,
        "written": 0,
        "skipped": 0,
        "failed": 0,
        "batch": 0,
        "batches": max(
            1,
            (total + int(run.configuration.get("batch_size", 16)) - 1)
            // int(run.configuration.get("batch_size", 16)),
        ),
        "attempt": 1,
    }
    latest = session.scalar(
        select(Event)
        .where(Event.run_id == run.id, Event.kind == "stage.progress")
        .order_by(Event.id.desc())
        .limit(1)
    )
    if latest is not None:
        progress.update(latest.payload)

    failures: list[CondensationFailureResponse] = []
    artifacts = _artifacts_for_run(session, run_id)
    provenance_artifact = next(
        (artifact for artifact in artifacts if artifact.kind == "condensation-provenance"),
        None,
    )
    failures_artifact = next(
        (
            artifact
            for artifact in artifacts
            if provenance_artifact is not None
            and artifact.kind == "condensation-failures"
            and artifact.attempt_id == provenance_artifact.attempt_id
        ),
        None,
    )
    if provenance_artifact is not None and failures_artifact is not None:
        try:
            store = FileSystemArtifactStore(settings.artifact_root)
            with store.open_read(provenance_artifact.key) as handle:
                provenance = json.load(handle)
            summary = provenance["summary"]
            if not isinstance(summary, dict):
                raise ValueError("invalid condensation summary")
            progress.update(summary)
            progress["completed"] = int(summary["total"])
            with store.open_read(failures_artifact.key) as binary_handle:
                with io.TextIOWrapper(binary_handle, encoding="utf-8-sig", newline="") as handle:
                    for row in csv.DictReader(handle):
                        failures.append(
                            CondensationFailureResponse(
                                material_id=str(row["material_id"]),
                                status=str(row["status"]),
                                error=str(row["error"]),
                            )
                        )
                        if len(failures) >= failure_limit:
                            break
        except (KeyError, TypeError, ValueError, csv.Error, UnicodeError) as error:
            raise DomainError(
                "condensation.preview_invalid",
                "The condensation preview artifacts are invalid",
                status_code=409,
            ) from error

    written = int(progress.get("written", 0))
    skipped = int(progress.get("skipped", 0))
    return CondensationPreviewResponse(
        total=int(progress.get("total", total)),
        completed=int(progress.get("completed", 0)),
        succeeded=int(progress.get("succeeded", written + skipped)),
        written=written,
        skipped=skipped,
        failed=int(progress.get("failed", 0)),
        batch=int(progress.get("batch", progress.get("batches", 0))),
        batches=int(progress.get("batches", 0)),
        attempt=int(progress.get("attempt", 1)),
        failures=failures,
    )


@router.get("/artifacts/{artifact_id}", response_model=ArtifactResponse)
def detail(
    artifact_id: uuid.UUID,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Artifact:
    return _authorized_artifact(session, artifact_id=artifact_id, user=user)


@router.get("/artifacts/{artifact_id}/download")
def download(
    artifact_id: uuid.UUID,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    artifact = _authorized_artifact(session, artifact_id=artifact_id, user=user)
    handle = FileSystemArtifactStore(settings.artifact_root).open_read(artifact.key)
    safe_filename = artifact.filename.replace('"', "")
    return StreamingResponse(
        handle,
        media_type=artifact.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
            "ETag": artifact.sha256,
        },
    )
