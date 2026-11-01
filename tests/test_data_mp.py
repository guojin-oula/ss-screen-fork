"""Tests for Materials Project dataset loading helpers."""

from __future__ import annotations

import json
from types import SimpleNamespace

from pymatgen.core import Lattice, Structure

from ssscreen.config import (
    MP_API_CHUNK_SIZE,
    MP_API_PAGE_RETRIES,
    MP_API_REQUEST_TIMEOUT_SECONDS,
    MP_API_RETRY_BACKOFF_SECONDS,
)
from ssscreen.data.mp import (
    MP_DATASET_PROVENANCE_ATTR,
    MP_OFFLINE_PROJECT_FIELDS,
    load_mp_dataset,
    load_mp_dataset_api,
    normalize_mp_documents,
)


def _structure() -> Structure:
    return Structure(Lattice.cubic(5.4), ["Ca", "S"], [[0, 0, 0], [0.5, 0.5, 0.5]])


def test_normalize_mp_documents_builds_screening_dataframe_schema():
    structure = _structure()
    docs = [
        SimpleNamespace(
            material_id="mp-1",
            composition={"Ca": 1, "S": 1},
            band_gap=0.0,
            energy_above_hull=0.003,
            structure=structure,
        )
    ]

    df = normalize_mp_documents(docs)

    assert list(df.index) == ["mp-1"]
    row = df.loc["mp-1"]
    assert row["composition"].reduced_formula == "CaS"
    assert row["reduced_composition"].reduced_formula == "CaS"
    assert row["nelems"] == 2
    assert row["band_gap"] == 0.0
    assert row["e_hull"] == 0.003
    assert row["source"] == "mp"
    assert row["structure"] is structure
    assert row["primitive_structure"].composition.reduced_formula == "CaS"


def test_normalize_mp_documents_unwraps_sqlalchemy_entity_rows():
    structure = _structure()
    document = SimpleNamespace(
        material_id="mp-1",
        composition={"Ca": 1, "S": 1},
        json_data={"band_gap": 0.0},
        energy_above_hull=0.003,
        structure=structure.as_dict(),
    )

    class FakeRow:
        _mapping = {"MaterialSummary": document}

    df = normalize_mp_documents([FakeRow()], source="mp-offline")

    assert list(df.index) == ["mp-1"]
    assert df.loc["mp-1", "source"] == "mp-offline"


def test_load_mp_dataset_defaults_to_mp_offline_backend(tmp_path):
    structure = _structure()
    calls = []

    class FakeColumn:
        def __init__(self, name):
            self.name = name

        def __ge__(self, value):
            return (f"{self.name}>=", value)

        def __le__(self, value):
            return (f"{self.name}<=", value)

        def is_(self, value):
            return (f"{self.name} is", value)

    class FakeMaterialSummary:
        energy_above_hull = FakeColumn("energy_above_hull")
        deprecated = FakeColumn("deprecated")

    class FakeClient:
        def __init__(self, database=None):
            calls.append(("init", database))

        def query_all(self, *criteria, project=None):
            calls.append(("query_all", criteria, project))
            return [
                SimpleNamespace(
                    material_id="mp-1",
                    composition={"Ca": 1, "S": 1},
                    json_data={
                        "band_gap": 0.0,
                        "builder_meta": {"database_version": "fixture-db"},
                    },
                    energy_above_hull=0.003,
                    deprecated=False,
                    structure=structure.as_dict(),
                )
            ]

    output = tmp_path / "mp.df"
    database = tmp_path / "mp-offline.db"
    database.write_bytes(b"sqlite-fixture")

    df = load_mp_dataset(
        output=output,
        max_e_hull=0.01,
        offline_db=database,
        database_reference="fixture-snapshot",
        offline_client_factory=FakeClient,
        material_summary_cls=FakeMaterialSummary,
    )

    assert output.exists()
    assert list(df.index) == ["mp-1"]
    assert df.loc["mp-1", "band_gap"] == 0.0
    assert df.loc["mp-1", "source"] == "mp-offline"
    assert calls[0] == ("init", database)
    assert calls[1] == (
        "query_all",
        (
            ("energy_above_hull>=", 0.0),
            ("energy_above_hull<=", 0.01),
            ("deprecated is", False),
        ),
        MP_OFFLINE_PROJECT_FIELDS,
    )
    provenance_path = tmp_path / "mp.df.provenance.json"
    assert provenance_path.exists()
    provenance = json.loads(provenance_path.read_text())
    assert provenance["query"]["deprecated"] is False
    assert provenance["database"]["sample_document_builder_meta"] == {
        "database_version": "fixture-db"
    }
    assert provenance["database"]["size_bytes"] == len(b"sqlite-fixture")
    assert provenance["database"]["reference"] == "fixture-snapshot"
    assert "path" not in provenance["database"]
    assert df.attrs[MP_DATASET_PROVENANCE_ATTR] == provenance


def test_load_mp_dataset_api_uses_mprester_without_explicit_api_key(tmp_path):
    structure = _structure()
    calls = []

    class FakeSummary:
        def search(self, **kwargs):
            calls.append(kwargs)
            return [
                {
                    "material_id": "mp-1",
                    "composition": {"Ca": 1, "S": 1},
                    "band_gap": 0.0,
                    "energy_above_hull": 0.003,
                    "structure": structure,
                }
            ]

    class FakeRester:
        def __init__(self):
            calls.append({"api_key": "not-passed"})
            self.materials = SimpleNamespace(summary=FakeSummary())
            self.db_version = "fixture-api-db"

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    output = tmp_path / "mp.df"

    df = load_mp_dataset_api(output=output, rester_factory=FakeRester)

    assert output.exists()
    assert list(df.index) == ["mp-1"]
    assert calls[0] == {"api_key": "not-passed"}
    assert calls[1]["fields"] == [
        "material_id",
        "composition",
        "band_gap",
        "energy_above_hull",
        "structure",
        "deprecated",
    ]
    assert calls[1]["deprecated"] is False
    assert calls[1]["chunk_size"] == MP_API_CHUNK_SIZE
    assert calls[1]["num_chunks"] == 1
    assert calls[1]["_page"] == 1
    assert calls[1]["_sort_fields"] == "material_id"
    provenance = json.loads((tmp_path / "mp.df.provenance.json").read_text())
    assert provenance["database"]["version"] == "fixture-api-db"
    assert provenance["request"] == {
        "chunk_size": MP_API_CHUNK_SIZE,
        "page_retries": MP_API_PAGE_RETRIES,
        "pagination": "explicit_pages",
        "retry_backoff_seconds": MP_API_RETRY_BACKOFF_SECONDS,
        "sort_fields": "material_id",
        "timeout_seconds": MP_API_REQUEST_TIMEOUT_SECONDS,
    }
    assert df.attrs[MP_DATASET_PROVENANCE_ATTR] == provenance


def test_load_mp_dataset_api_extends_default_mprester_timeout(tmp_path, monkeypatch):
    structure = _structure()
    calls = []

    class FakeSummary:
        def search(self, **kwargs):
            calls.append(kwargs)
            return [
                {
                    "material_id": "mp-1",
                    "composition": {"Ca": 1, "S": 1},
                    "band_gap": 0.0,
                    "energy_above_hull": 0.003,
                    "structure": structure,
                }
            ]

    class FakeRester:
        def __init__(self, *, timeout):
            calls.append({"timeout": timeout})
            self.materials = SimpleNamespace(summary=FakeSummary())
            self.db_version = "fixture-api-db"

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("mp_api.client.MPRester", FakeRester)

    load_mp_dataset_api(output=tmp_path / "mp.df")

    assert calls[0] == {"timeout": MP_API_REQUEST_TIMEOUT_SECONDS}
    assert calls[1]["chunk_size"] == MP_API_CHUNK_SIZE


def test_load_mp_dataset_api_retries_only_the_failed_page(tmp_path, monkeypatch):
    structure = _structure()
    calls = []

    class FakeSummary:
        def search(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise RuntimeError("transient page failure")
            return [
                {
                    "material_id": "mp-1",
                    "composition": {"Ca": 1, "S": 1},
                    "band_gap": 0.0,
                    "energy_above_hull": 0.003,
                    "structure": structure,
                }
            ]

    class FakeRester:
        def __init__(self):
            self.materials = SimpleNamespace(summary=FakeSummary())
            self.db_version = "fixture-api-db"

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("ssscreen.data.mp.time.sleep", lambda _seconds: None)

    df = load_mp_dataset_api(output=tmp_path / "mp.df", rester_factory=FakeRester)

    assert list(df.index) == ["mp-1"]
    assert len(calls) == 2
    assert calls[0]["_page"] == calls[1]["_page"] == 1
