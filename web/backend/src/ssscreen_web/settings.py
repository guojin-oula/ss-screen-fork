from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+psycopg://ssscreen:ssscreen@127.0.0.1:5432/ssscreen"
    redis_url: str = "redis://127.0.0.1:6379/0"
    artifact_root: Path = Path("/vepfs-mlp2/project-battery/zuolong/ss-screen-web-data/artifacts")
    attempt_sandbox_root: Path = Path(
        "/vepfs-mlp2/project-battery/zuolong/ss-screen-web-data/attempt-sandboxes"
    )
    uploads_quarantine_root: Path = Path(
        "/vepfs-mlp2/project-battery/zuolong/ss-screen-web-data/uploads-quarantine"
    )
    mp_offline_database_path: Path | None = None
    mp_offline_database_reference: str = "mp-offline-server-snapshot"
    ssscreen_core_revision: str = "development-worktree"
    workspace_root: Path = Path("/vepfs-mlp2/project-battery/zuolong/ss-screen-learning-20260722")
    dev_auth_enabled: bool = True
    dev_user_subject: str = "dev-local-user"
    dev_user_display_name: str = "SS-Screen Developer"
    cors_origins: Annotated[tuple[str, ...], NoDecode] = ("http://localhost:5173",)
    log_level: str = "INFO"
    sse_poll_seconds: float = 0.5
    sse_heartbeat_seconds: float = 15.0
    celery_task_always_eager: bool = False
    outbox_reconcile_seconds: float = 5.0
    outbox_redelivery_seconds: float = 30.0
    demo_task_stale_seconds: float = 300.0
    mp_dataset_task_stale_seconds: float = 7200.0
    wbm_xyz_upload_max_bytes: int = 2 * 1024 * 1024 * 1024
    wbm_summary_upload_max_bytes: int = 256 * 1024 * 1024

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        return value

    @field_validator("ssscreen_core_revision")
    @classmethod
    def validate_core_revision(cls, value: str) -> str:
        revision = value.strip()
        if not revision:
            raise ValueError("SSSCREEN_CORE_REVISION must not be empty")
        return revision

    @field_validator("wbm_xyz_upload_max_bytes", "wbm_summary_upload_max_bytes")
    @classmethod
    def validate_upload_limit(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("WBM upload byte limits must be positive")
        return value

    @model_validator(mode="after")
    def validate_security_boundary(self) -> Settings:
        if self.app_env != "development" and self.dev_auth_enabled:
            raise ValueError("DEV_AUTH_ENABLED is only permitted when APP_ENV=development")
        workspace = self.workspace_root.expanduser().resolve(strict=False)
        storage_roots = {
            "ARTIFACT_ROOT": self.artifact_root,
            "ATTEMPT_SANDBOX_ROOT": self.attempt_sandbox_root,
            "UPLOADS_QUARANTINE_ROOT": self.uploads_quarantine_root,
        }
        if self.app_env != "development":
            if self.ssscreen_core_revision == "development-worktree":
                raise ValueError(
                    "SSSCREEN_CORE_REVISION must identify the deployed source in production"
                )
            for name, configured_root in storage_roots.items():
                root = configured_root.expanduser().resolve(strict=False)
                if root.is_relative_to(workspace):
                    raise ValueError(f"{name} must be outside the Git workspace in production")
            if self.mp_offline_database_path is not None:
                database = self.mp_offline_database_path.expanduser().resolve(strict=False)
                if database.is_relative_to(workspace):
                    raise ValueError(
                        "MP_OFFLINE_DATABASE_PATH must be outside the Git workspace in production"
                    )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
