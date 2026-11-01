from __future__ import annotations

import os

import pytest

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://ssscreen:ssscreen@127.0.0.1:5432/ssscreen_test"
)
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")

from ssscreen_web.infrastructure import models  # noqa: E402, F401
from ssscreen_web.infrastructure.database import Base, get_engine  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database(request: pytest.FixtureRequest):
    if "integration" not in str(request.path):
        yield
        return
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
