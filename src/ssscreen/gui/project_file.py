"""Portable single-file project containers for the desktop workbench."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

PROJECT_FORMAT = "ss-screen-project"
PROJECT_FORMAT_VERSION = 1
STAGE_PREFIXES = tuple(f"{index:02d}_" for index in range(1, 13))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_project_artifacts(project_root: Path) -> list[Path]:
    """Return deterministic Stage 01--12 files eligible for the project container."""
    root = project_root.resolve()
    files: list[Path] = []
    for directory in sorted(root.iterdir() if root.exists() else []):
        if not directory.is_dir() or not directory.name.startswith(STAGE_PREFIXES):
            continue
        files.extend(path for path in directory.rglob("*") if path.is_file())
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def create_project_file(
    project_root: str | Path,
    destination: str | Path,
    *,
    project_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create an atomic ``.ssproject`` ZIP64 container and return its manifest."""
    root = Path(project_root).expanduser().resolve()
    target = Path(destination).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    artifacts = iter_project_artifacts(root)
    entries = []
    for path in artifacts:
        relative = path.relative_to(root).as_posix()
        entries.append({"path": relative, "size": path.stat().st_size, "sha256": _sha256(path)})

    created = datetime.now(timezone.utc).isoformat()
    project = {
        "format": PROJECT_FORMAT,
        "format_version": PROJECT_FORMAT_VERSION,
        "name": root.name,
        "created_at": created,
        "settings": project_settings or {},
    }
    manifest = {
        "format": PROJECT_FORMAT,
        "format_version": PROJECT_FORMAT_VERSION,
        "created_at": created,
        "artifact_count": len(entries),
        "total_bytes": sum(entry["size"] for entry in entries),
        "artifacts": entries,
    }

    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    os.close(file_descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True
        ) as archive:
            archive.writestr("project.json", json.dumps(project, ensure_ascii=False, indent=2))
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            for path, entry in zip(artifacts, entries, strict=True):
                archive.write(path, f"artifacts/{entry['path']}")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return manifest


def inspect_project_file(project_file: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read and validate project metadata without extracting artifacts."""
    path = Path(project_file).expanduser().resolve()
    with zipfile.ZipFile(path) as archive:
        project = json.loads(archive.read("project.json"))
        manifest = json.loads(archive.read("manifest.json"))
    if project.get("format") != PROJECT_FORMAT or manifest.get("format") != PROJECT_FORMAT:
        raise ValueError("not an SS-Screen project file")
    if project.get("format_version") != PROJECT_FORMAT_VERSION:
        raise ValueError(f"unsupported SS-Screen project version: {project.get('format_version')}")
    return project, manifest


def extract_project_file(project_file: str | Path, destination: str | Path) -> dict[str, Any]:
    """Extract a project safely and verify every artifact checksum."""
    source = Path(project_file).expanduser().resolve()
    target = Path(destination).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    project, manifest = inspect_project_file(source)
    expected = {entry["path"]: entry for entry in manifest.get("artifacts", [])}

    with zipfile.ZipFile(source) as archive:
        for member in archive.infolist():
            member_path = PurePosixPath(member.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValueError(f"unsafe project member: {member.filename}")
            if not member.filename.startswith("artifacts/") or member.is_dir():
                continue
            relative = PurePosixPath(*member_path.parts[1:]).as_posix()
            if relative not in expected:
                raise ValueError(f"unmanifested project artifact: {relative}")
            output = target.joinpath(*PurePosixPath(relative).parts)
            output.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as reader, output.open("wb") as writer:
                while chunk := reader.read(1024 * 1024):
                    writer.write(chunk)

    for relative, entry in expected.items():
        output = target.joinpath(*PurePosixPath(relative).parts)
        if not output.is_file():
            raise ValueError(f"missing project artifact: {relative}")
        if output.stat().st_size != entry["size"] or _sha256(output) != entry["sha256"]:
            raise ValueError(f"project artifact checksum mismatch: {relative}")

    metadata_dir = target / ".ssscreen"
    metadata_dir.mkdir(exist_ok=True)
    (metadata_dir / "project.json").write_text(
        json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (metadata_dir / "source.txt").write_text(str(source), encoding="utf-8")
    return manifest
