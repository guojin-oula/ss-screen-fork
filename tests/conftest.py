"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "data" / "condensed"


@pytest.fixture
def fixture_dir() -> Path:
    return FIXTURE_DIR


@pytest.fixture
def cese2_condensed() -> dict[str, dict]:
    """Real robocrys condensed dicts for CeSe2 polymorphs.

    mp-1080296 and mp-1080351 share an identical environment (CeSe4 tetrahedron
    + linear Se), so envmatch collapses them into one group. mp-1080265 has a
    tetrahedral CeSe4 but a *bent* (120°) Se — different environment, must NOT
    join the group. mp-1080248 (Ibam, 4-coordinate / L-shaped) is also
    different.
    """
    from monty.serialization import loadfn

    return {
        "mp-1080296": loadfn(str(FIXTURE_DIR / "mp-1080296.json")),
        "mp-1080351": loadfn(str(FIXTURE_DIR / "mp-1080351.json")),
        "mp-1080265": loadfn(str(FIXTURE_DIR / "mp-1080265.json")),
        "mp-1080248": loadfn(str(FIXTURE_DIR / "mp-1080248.json")),
    }
