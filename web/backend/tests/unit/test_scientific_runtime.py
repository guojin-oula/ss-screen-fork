import pytest

from ssscreen_web.application import scientific_runtime
from ssscreen_web.application.scientific_runtime import (
    core_source_sha256,
    require_frozen_scientific_runtime,
    require_scientific_runtime,
)
from ssscreen_web.domain.errors import DomainError
from ssscreen_web.settings import Settings


def test_scientific_runtime_records_consistent_version_and_source_hash() -> None:
    identity = require_scientific_runtime(
        Settings(_env_file=None, ssscreen_core_revision="git:test")
    )

    assert identity.distribution == "ss-screen"
    assert identity.version == identity.distribution_version == "1.0"
    assert identity.source_sha256 == core_source_sha256()
    assert len(identity.source_sha256) == 64
    assert identity.revision == "git:test"


def test_scientific_runtime_rejects_distribution_version_drift(monkeypatch) -> None:
    monkeypatch.setattr(scientific_runtime, "core_distribution_version", lambda: "0.1.0")

    with pytest.raises(DomainError, match="versions do not match") as error:
        require_scientific_runtime(Settings(_env_file=None))

    assert error.value.code == "runtime.core_version_mismatch"


def test_scientific_runtime_rejects_identity_change_after_run_creation() -> None:
    frozen = require_scientific_runtime(
        Settings(_env_file=None, ssscreen_core_revision="git:revision-a")
    ).as_dict()

    with pytest.raises(DomainError, match="changed after this Run was created") as error:
        require_frozen_scientific_runtime(
            Settings(_env_file=None, ssscreen_core_revision="git:revision-b"), frozen
        )

    assert error.value.code == "runtime.core_identity_changed"
