from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from ssscreen.config import Thresholds

from ssscreen_web.api.dependencies import get_current_user
from ssscreen_web.api.schemas import RunCreate, RunResponse, TaskResponse
from ssscreen_web.application.runs import cancel_run, create_run, start_run
from ssscreen_web.application.scientific_runtime import (
    require_frozen_scientific_runtime,
    require_scientific_runtime,
)
from ssscreen_web.application.upload_lifecycle import cleanup_wbm_quarantine
from ssscreen_web.domain.errors import DomainError
from ssscreen_web.infrastructure.artifacts import FileSystemArtifactStore
from ssscreen_web.infrastructure.database import get_db
from ssscreen_web.infrastructure.models import Artifact, Attempt, Dataset, Run, Task, User
from ssscreen_web.infrastructure.repositories import require_project_role
from ssscreen_web.settings import Settings, get_settings
from ssscreen_web.workers.celery_app import dispatch_pending_outbox

router = APIRouter(prefix="/api/v1", tags=["runs"])


def _get_authorized_run(
    session: Session, *, run_id: uuid.UUID, user: User, write: bool = False
) -> Run:
    run = session.get(Run, run_id)
    if run is None:
        raise DomainError("run.not_found", "Run was not found", status_code=404)
    require_project_role(session, project_id=run.project_id, user_id=user.id, write=write)
    return run


@router.post(
    "/projects/{project_id}/runs", response_model=RunResponse, status_code=status.HTTP_201_CREATED
)
def create(
    project_id: uuid.UUID,
    body: RunCreate,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> Run:
    require_project_role(session, project_id=project_id, user_id=user.id, write=True)
    if body.pipeline == "stage-1-mp-offline":
        database = settings.mp_offline_database_path
        if database is None or not database.expanduser().resolve(strict=False).is_file():
            raise DomainError(
                "dataset.offline_not_configured",
                "The server has no available Materials Project offline snapshot configured",
                status_code=503,
            )
        identity = require_scientific_runtime(settings)
        configuration = body.model_dump()
        configuration["scientific_runtime"] = identity.as_dict()
    elif body.pipeline == "stage-1a-composition":
        dataset = session.get(Dataset, body.dataset_id)
        if dataset is None or dataset.project_id != project_id:
            raise DomainError("dataset.not_found", "Dataset was not found", status_code=404)
        artifact = session.get(Artifact, dataset.artifact_id)
        if artifact is None or artifact.kind not in {
            "mp-normalized-dataframe",
            "wbm-normalized-dataframe",
        }:
            raise DomainError(
                "composition.input_unsupported",
                "The selected Dataset is not a supported normalized input",
            )
        identity = require_scientific_runtime(settings)
        configuration = body.model_dump(mode="json")
        configuration.update(
            {
                "message": f"组成筛选：{dataset.label}",
                "dataset_id": str(dataset.id),
                "dataset_kind": dataset.kind,
                "dataset_label": dataset.label,
                "dataset_artifact_id": str(artifact.id),
                "dataset_artifact_sha256": artifact.sha256,
                "excluded_elements": sorted(Thresholds.default(body.nelems).excluded_elements),
                "scientific_runtime": identity.as_dict(),
            }
        )
    elif body.pipeline == "stage-2-condensation":
        composition_run = session.get(Run, body.composition_run_id)
        if (
            composition_run is None
            or composition_run.project_id != project_id
            or composition_run.pipeline_version != "stage-1a-composition-v1"
        ):
            raise DomainError(
                "condensation.composition_run_not_found",
                "The selected composition Run was not found",
                status_code=404,
            )
        if composition_run.status != "SUCCEEDED":
            raise DomainError(
                "condensation.composition_run_incomplete",
                "The selected composition Run has not succeeded",
                status_code=409,
            )
        artifacts = list(
            session.scalars(
                select(Artifact)
                .join(Attempt, Artifact.attempt_id == Attempt.id)
                .join(Task, Attempt.task_id == Task.id)
                .where(Task.run_id == composition_run.id)
                .order_by(Artifact.created_at.desc())
            ).all()
        )
        candidates = next(
            (artifact for artifact in artifacts if artifact.kind == "composition-candidates"),
            None,
        )
        provenance_artifact = next(
            (
                artifact
                for artifact in artifacts
                if candidates is not None
                and artifact.kind == "composition-provenance"
                and artifact.attempt_id == candidates.attempt_id
            ),
            None,
        )
        if candidates is None or provenance_artifact is None:
            raise DomainError(
                "condensation.candidates_unavailable",
                "The composition candidate artifacts are unavailable",
                status_code=409,
            )
        try:
            dataset_id = uuid.UUID(str(composition_run.configuration["dataset_id"]))
            dataset_artifact_id = uuid.UUID(
                str(composition_run.configuration["dataset_artifact_id"])
            )
        except (KeyError, ValueError) as error:
            raise DomainError(
                "condensation.source_invalid",
                "The composition Run has invalid frozen Dataset provenance",
                status_code=409,
            ) from error
        dataset = session.get(Dataset, dataset_id)
        dataset_artifact = session.get(Artifact, dataset_artifact_id)
        if (
            dataset is None
            or dataset.project_id != project_id
            or dataset.artifact_id != dataset_artifact_id
            or dataset_artifact is None
            or dataset_artifact.sha256
            != composition_run.configuration.get("dataset_artifact_sha256")
        ):
            raise DomainError(
                "condensation.dataset_unavailable",
                "The frozen normalized Dataset is unavailable",
                status_code=409,
            )
        try:
            with FileSystemArtifactStore(settings.artifact_root).open_read(
                provenance_artifact.key
            ) as handle:
                candidate_provenance = json.load(handle)
            candidate_count = int(candidate_provenance["row_count"])
            if candidate_count < 0:
                raise ValueError("negative candidate count")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise DomainError(
                "condensation.candidates_invalid",
                "The composition candidate provenance is invalid",
                status_code=409,
            ) from error
        identity = require_scientific_runtime(settings)
        configuration = body.model_dump(mode="json")
        configuration.update(
            {
                "message": f"结构描述：{composition_run.configuration.get('dataset_label', dataset.label)}",
                "composition_run_id": str(composition_run.id),
                "candidate_count": candidate_count,
                "candidate_artifact_id": str(candidates.id),
                "candidate_artifact_sha256": candidates.sha256,
                "candidate_provenance_artifact_id": str(provenance_artifact.id),
                "candidate_provenance_artifact_sha256": provenance_artifact.sha256,
                "dataset_id": str(dataset.id),
                "dataset_kind": dataset.kind,
                "dataset_label": dataset.label,
                "dataset_artifact_id": str(dataset_artifact.id),
                "dataset_artifact_sha256": dataset_artifact.sha256,
                "scientific_runtime": identity.as_dict(),
            }
        )
    else:
        configuration = body.model_dump()
    return create_run(session, project_id=project_id, configuration=configuration, user=user)


@router.get("/projects/{project_id}/runs", response_model=list[RunResponse])
def list_for_project(
    project_id: uuid.UUID,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Run]:
    require_project_role(session, project_id=project_id, user_id=user.id)
    return list(
        session.scalars(
            select(Run).where(Run.project_id == project_id).order_by(Run.created_at.desc())
        ).all()
    )


@router.get("/runs/{run_id}", response_model=RunResponse)
def detail(
    run_id: uuid.UUID,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Run:
    return _get_authorized_run(session, run_id=run_id, user=user)


@router.post("/runs/{run_id}/actions/start", response_model=TaskResponse)
def start(
    run_id: uuid.UUID,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> object:
    run = _get_authorized_run(session, run_id=run_id, user=user, write=True)
    if run.pipeline_version in {
        "stage-1-mp-offline-v1",
        "stage-1-wbm-upload-v1",
        "stage-1a-composition-v1",
        "stage-2-condensation-v1",
    }:
        require_frozen_scientific_runtime(settings, run.configuration.get("scientific_runtime"))
    task = start_run(session, run=run, user=user)
    dispatch_pending_outbox()
    return task


@router.post("/runs/{run_id}/actions/cancel", response_model=RunResponse)
def cancel(
    run_id: uuid.UUID,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> Run:
    run = _get_authorized_run(session, run_id=run_id, user=user, write=True)
    cancelled = cancel_run(session, run=run, user=user)
    if cancelled.status == "CANCELLED":
        cleanup_wbm_quarantine(dict(cancelled.configuration), settings=settings)
    return cancelled
