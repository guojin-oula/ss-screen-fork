from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from ssscreen_web.api.dependencies import get_current_user
from ssscreen_web.api.schemas import RunResponse
from ssscreen_web.application.runs import create_run
from ssscreen_web.application.scientific_runtime import require_scientific_runtime
from ssscreen_web.domain.errors import DomainError
from ssscreen_web.infrastructure.artifacts import FileSystemArtifactStore, StoredArtifact
from ssscreen_web.infrastructure.database import get_db
from ssscreen_web.infrastructure.models import Run, User
from ssscreen_web.infrastructure.repositories import require_project_role
from ssscreen_web.settings import Settings, get_settings

router = APIRouter(prefix="/api/v1", tags=["uploads"])

_XYZ_SUFFIXES = {".xyz", ".extxyz"}
_SUMMARY_SUFFIXES = {".csv", ".tsv"}
_XYZ_CONTENT_TYPES = {"application/octet-stream", "chemical/x-xyz", "text/plain"}
_SUMMARY_CONTENT_TYPES = {
    "application/octet-stream",
    "application/vnd.ms-excel",
    "text/csv",
    "text/plain",
    "text/tab-separated-values",
}


def _validated_filename(upload: UploadFile, *, suffixes: set[str], role: str) -> str:
    filename = upload.filename or ""
    if (
        not filename
        or len(filename) > 255
        or "/" in filename
        or "\\" in filename
        or filename in {".", ".."}
        or Path(filename).is_absolute()
    ):
        raise DomainError("upload.invalid_filename", f"The {role} filename is unsafe")
    if Path(filename).suffix.lower() not in suffixes:
        allowed = ", ".join(sorted(suffixes))
        raise DomainError("upload.invalid_extension", f"The {role} file must use one of: {allowed}")
    return filename


def _validated_content_type(upload: UploadFile, *, allowed: set[str], role: str) -> str:
    content_type = (upload.content_type or "application/octet-stream").lower()
    if content_type not in allowed:
        raise DomainError(
            "upload.invalid_content_type", f"The {role} file content type is not accepted"
        )
    return content_type


def _metadata(*, stored: StoredArtifact, filename: str, content_type: str) -> dict[str, object]:
    return {
        "key": stored.key,
        "filename": filename,
        "content_type": content_type,
        "size_bytes": stored.size_bytes,
        "sha256": stored.sha256,
    }


@router.post(
    "/projects/{project_id}/datasets/wbm-upload",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_wbm_upload(
    project_id: uuid.UUID,
    dataset_label: Annotated[str, Form(min_length=1, max_length=200)],
    xyz_file: Annotated[UploadFile, File()],
    summary_file: Annotated[UploadFile | None, File()] = None,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> Run:
    require_project_role(session, project_id=project_id, user_id=user.id, write=True)
    label = dataset_label.strip()
    if not label:
        raise DomainError("upload.invalid_label", "Dataset label must not be blank")
    xyz_filename = _validated_filename(xyz_file, suffixes=_XYZ_SUFFIXES, role="structure")
    xyz_content_type = _validated_content_type(
        xyz_file, allowed=_XYZ_CONTENT_TYPES, role="structure"
    )
    summary_filename: str | None = None
    summary_content_type: str | None = None
    if summary_file is not None:
        summary_filename = _validated_filename(
            summary_file, suffixes=_SUMMARY_SUFFIXES, role="summary"
        )
        summary_content_type = _validated_content_type(
            summary_file, allowed=_SUMMARY_CONTENT_TYPES, role="summary"
        )

    identity = require_scientific_runtime(settings)
    upload_id = uuid.uuid4()
    quarantine = FileSystemArtifactStore(settings.uploads_quarantine_root)
    quarantine.ensure_ready()
    stored_keys: list[str] = []
    try:
        xyz_key = f"projects/{project_id}/uploads/{upload_id}/structures.extxyz"
        xyz_stored = quarantine.put_stream(
            xyz_file.file, key=xyz_key, max_bytes=settings.wbm_xyz_upload_max_bytes
        )
        stored_keys.append(xyz_key)
        summary_stored: StoredArtifact | None = None
        summary_key: str | None = None
        if summary_file is not None:
            suffix = Path(summary_filename or "summary.csv").suffix.lower()
            summary_key = f"projects/{project_id}/uploads/{upload_id}/summary{suffix}"
            summary_stored = quarantine.put_stream(
                summary_file.file,
                key=summary_key,
                max_bytes=settings.wbm_summary_upload_max_bytes,
            )
            stored_keys.append(summary_key)

        upload_configuration: dict[str, object] = {
            "id": str(upload_id),
            "structures": _metadata(
                stored=xyz_stored,
                filename=xyz_filename,
                content_type=xyz_content_type,
            ),
        }
        if summary_stored is not None:
            upload_configuration["summary"] = _metadata(
                stored=summary_stored,
                filename=summary_filename or "summary.csv",
                content_type=summary_content_type or "application/octet-stream",
            )
        configuration = {
            "pipeline": "stage-1-wbm-upload",
            "message": f"上传数据集：{label}",
            "dataset_label": label,
            "scientific_runtime": identity.as_dict(),
            "upload": upload_configuration,
        }
        return create_run(session, project_id=project_id, configuration=configuration, user=user)
    except Exception:
        for key in stored_keys:
            quarantine.delete(key)
        raise
