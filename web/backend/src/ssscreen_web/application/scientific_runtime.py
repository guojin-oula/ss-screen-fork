from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import ssscreen

from ssscreen_web.domain.errors import DomainError
from ssscreen_web.settings import Settings

CORE_DISTRIBUTION = "ss-screen"


@dataclass(frozen=True)
class ScientificRuntimeIdentity:
    distribution: str
    version: str
    distribution_version: str
    source_sha256: str
    revision: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@lru_cache(maxsize=1)
def core_source_sha256() -> str:
    package_root = Path(ssscreen.__file__).resolve().parent
    digest = hashlib.sha256()
    sources = sorted(package_root.rglob("*.py"), key=lambda path: path.relative_to(package_root))
    if not sources:
        raise DomainError(
            "runtime.core_source_unavailable",
            "The scientific core source files are unavailable",
            status_code=503,
        )
    for source in sources:
        relative = source.relative_to(package_root).as_posix().encode()
        digest.update(relative)
        digest.update(b"\0")
        digest.update(source.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def core_distribution_version() -> str:
    try:
        return version(CORE_DISTRIBUTION)
    except PackageNotFoundError as error:
        raise DomainError(
            "runtime.core_distribution_missing",
            "The scientific core distribution metadata is unavailable",
            status_code=503,
        ) from error


def scientific_runtime_identity(settings: Settings) -> ScientificRuntimeIdentity:
    return ScientificRuntimeIdentity(
        distribution=CORE_DISTRIBUTION,
        version=ssscreen.__version__,
        distribution_version=core_distribution_version(),
        source_sha256=core_source_sha256(),
        revision=settings.ssscreen_core_revision,
    )


def require_scientific_runtime(settings: Settings) -> ScientificRuntimeIdentity:
    identity = scientific_runtime_identity(settings)
    if identity.version != identity.distribution_version:
        raise DomainError(
            "runtime.core_version_mismatch",
            "The scientific core source and distribution versions do not match",
            status_code=503,
        )
    return identity


def require_frozen_scientific_runtime(
    settings: Settings, frozen: object
) -> ScientificRuntimeIdentity:
    current = require_scientific_runtime(settings)
    if not isinstance(frozen, Mapping) or dict(frozen) != current.as_dict():
        raise DomainError(
            "runtime.core_identity_changed",
            "The scientific core identity changed after this Run was created; create a new Run",
            status_code=409,
        )
    return current
