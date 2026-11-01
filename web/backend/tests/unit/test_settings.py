from pathlib import Path

import pytest
from pydantic import ValidationError

from ssscreen_web.settings import Settings


def test_development_auth_is_rejected_outside_development() -> None:
    with pytest.raises(ValidationError, match="DEV_AUTH_ENABLED"):
        Settings(app_env="production", dev_auth_enabled=True)


def test_production_artifact_root_must_be_outside_workspace(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="outside the Git workspace"):
        Settings(
            app_env="production",
            dev_auth_enabled=False,
            ssscreen_core_revision="git:test",
            workspace_root=tmp_path,
            artifact_root=tmp_path / "artifacts",
        )


def test_production_mp_snapshot_must_be_outside_workspace(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="MP_OFFLINE_DATABASE_PATH"):
        Settings(
            app_env="production",
            dev_auth_enabled=False,
            ssscreen_core_revision="git:test",
            workspace_root=tmp_path,
            artifact_root=tmp_path.parent / "artifacts",
            attempt_sandbox_root=tmp_path.parent / "sandboxes",
            uploads_quarantine_root=tmp_path.parent / "quarantine",
            mp_offline_database_path=tmp_path / "default.db",
        )


def test_production_requires_deployed_core_revision(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="SSSCREEN_CORE_REVISION"):
        Settings(
            app_env="production",
            dev_auth_enabled=False,
            workspace_root=tmp_path,
            artifact_root=tmp_path.parent / "artifacts",
            attempt_sandbox_root=tmp_path.parent / "sandboxes",
            uploads_quarantine_root=tmp_path.parent / "quarantine",
        )


def test_cors_origins_accept_comma_separated_environment(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173, http://127.0.0.1:5173")
    settings = Settings()
    assert settings.cors_origins == (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )


def test_wbm_upload_limits_must_be_positive() -> None:
    with pytest.raises(ValidationError, match="upload byte limits"):
        Settings(wbm_xyz_upload_max_bytes=0)
