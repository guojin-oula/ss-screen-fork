from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from ssscreen_web.domain.errors import DomainError

_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$")


@dataclass(frozen=True)
class StoredArtifact:
    key: str
    size_bytes: int
    sha256: str


class FileSystemArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve(strict=False)

    def ensure_ready(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.root.is_dir() or not os.access(self.root, os.W_OK | os.X_OK):
            raise DomainError(
                "artifact.root_not_writable", f"Artifact root is not writable: {self.root}"
            )
        handle = tempfile.NamedTemporaryFile(dir=self.root, prefix=".readiness-", delete=False)
        probe = Path(handle.name)
        try:
            with handle:
                handle.write(b"ssscreen-web-readiness\n")
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as error:
            raise DomainError(
                "artifact.root_not_writable", f"Artifact root is not writable: {self.root}"
            ) from error
        finally:
            probe.unlink(missing_ok=True)

    def _path(self, key: str) -> Path:
        if "\x00" in key or key.startswith(("/", "\\")):
            raise DomainError("artifact.invalid_key", "Artifact key must be a relative logical key")
        parts = Path(key).parts
        if not parts or any(
            part in {"", ".", ".."} or not _SEGMENT.fullmatch(part) for part in parts
        ):
            raise DomainError("artifact.invalid_key", "Artifact key contains an unsafe segment")
        candidate = self.root.joinpath(*parts)
        resolved = candidate.resolve(strict=False)
        if not resolved.is_relative_to(self.root):
            raise DomainError("artifact.invalid_key", "Artifact key escapes the configured root")
        return candidate

    def put_bytes(
        self, content: bytes, *, key: str, expected_sha256: str | None = None
    ) -> StoredArtifact:
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise DomainError("artifact.immutable", "Artifact already exists", status_code=409)
        if target.parent.resolve(strict=True).is_relative_to(self.root) is False:
            raise DomainError("artifact.invalid_key", "Artifact parent escapes the configured root")
        digest = hashlib.sha256(content).hexdigest()
        if expected_sha256 is not None and digest != expected_sha256:
            raise DomainError("artifact.hash_mismatch", "Artifact SHA-256 does not match")
        handle = tempfile.NamedTemporaryFile(dir=target.parent, prefix=".upload-", delete=False)
        temp_path = Path(handle.name)
        try:
            with handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temp_path, target)
            except FileExistsError as error:
                raise DomainError(
                    "artifact.immutable", "Artifact already exists", status_code=409
                ) from error
            temp_path.unlink()
            directory_fd = os.open(target.parent, os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
        return StoredArtifact(key=key, size_bytes=len(content), sha256=digest)

    def put_file(self, source: Path, *, key: str, content_type: str) -> StoredArtifact:
        del content_type
        if source.is_symlink() or not source.is_file():
            raise DomainError("artifact.invalid_source", "Artifact source must be a regular file")
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise DomainError("artifact.immutable", "Artifact already exists", status_code=409)
        if target.parent.resolve(strict=True).is_relative_to(self.root) is False:
            raise DomainError("artifact.invalid_key", "Artifact parent escapes the configured root")
        digest = hashlib.sha256()
        size_bytes = 0
        handle = tempfile.NamedTemporaryFile(dir=target.parent, prefix=".upload-", delete=False)
        temp_path = Path(handle.name)
        try:
            with source.open("rb") as source_handle, handle:
                for chunk in iter(lambda: source_handle.read(1024 * 1024), b""):
                    handle.write(chunk)
                    digest.update(chunk)
                    size_bytes += len(chunk)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temp_path, target)
            except FileExistsError as error:
                raise DomainError(
                    "artifact.immutable", "Artifact already exists", status_code=409
                ) from error
            temp_path.unlink()
            directory_fd = os.open(target.parent, os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
        return StoredArtifact(key=key, size_bytes=size_bytes, sha256=digest.hexdigest())

    def put_stream(self, source: BinaryIO, *, key: str, max_bytes: int) -> StoredArtifact:
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise DomainError("artifact.immutable", "Artifact already exists", status_code=409)
        if target.parent.resolve(strict=True).is_relative_to(self.root) is False:
            raise DomainError("artifact.invalid_key", "Artifact parent escapes the configured root")
        digest = hashlib.sha256()
        size_bytes = 0
        handle = tempfile.NamedTemporaryFile(dir=target.parent, prefix=".upload-", delete=False)
        temp_path = Path(handle.name)
        try:
            with handle:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    size_bytes += len(chunk)
                    if size_bytes > max_bytes:
                        raise DomainError(
                            "upload.too_large",
                            f"Upload exceeds the configured {max_bytes}-byte limit",
                            status_code=413,
                        )
                    handle.write(chunk)
                    digest.update(chunk)
                if size_bytes == 0:
                    raise DomainError("upload.empty", "Uploaded files must not be empty")
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temp_path, target)
            except FileExistsError as error:
                raise DomainError(
                    "artifact.immutable", "Artifact already exists", status_code=409
                ) from error
            temp_path.unlink()
            directory_fd = os.open(target.parent, os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
        return StoredArtifact(key=key, size_bytes=size_bytes, sha256=digest.hexdigest())

    def open_read(self, key: str) -> BinaryIO:
        path = self._path(key)
        if path.is_symlink() or not path.is_file():
            raise DomainError(
                "artifact.not_found", "Artifact content was not found", status_code=404
            )
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(self.root):
            raise DomainError("artifact.invalid_key", "Artifact target escapes the configured root")
        return path.open("rb")

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.is_symlink():
            raise DomainError("artifact.invalid_key", "Artifact target must not be a symbolic link")
        path.unlink(missing_ok=True)
