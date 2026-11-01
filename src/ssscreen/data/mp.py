"""Materials Project dataset loading.

The default loader uses ``mp_offline`` so the CLI can run in network-isolated
environments. The live API loader is still available explicitly and uses
``MPRester()`` without passing an API key, so standard pymatgen/mp-api
configuration files such as ``~/.pmgrc.yaml`` can own credentials.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime, timezone
from functools import partial
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import pandas as pd
from pymatgen.core import Composition, Structure

from ..config import (
    MP_API_CHUNK_SIZE,
    MP_API_PAGE_RETRIES,
    MP_API_REQUEST_TIMEOUT_SECONDS,
    MP_API_RETRY_BACKOFF_SECONDS,
)

MP_SUMMARY_FIELDS = [
    "material_id",
    "composition",
    "band_gap",
    "energy_above_hull",
    "structure",
    "deprecated",
]

MP_OFFLINE_PROJECT_FIELDS = [
    "material_id",
    "composition",
    "structure",
    "energy_above_hull",
    "deprecated",
    "json_data",
]
MP_DATASET_PROVENANCE_SCHEMA_VERSION = 1
MP_DATASET_PROVENANCE_ATTR = "ssscreen_mp_dataset_provenance"


def unwrap_mp_offline_row(row: Any) -> Any:
    """Unwrap the one-entity SQLAlchemy Row returned by ``MPOffline.query_all``."""
    if isinstance(row, Mapping):
        return row
    mapping = getattr(row, "_mapping", None)
    if mapping is not None:
        values = list(mapping.values())
        if len(values) == 1:
            return values[0]
        return row
    if isinstance(row, (tuple, list)) and len(row) == 1:
        return row[0]
    return row


def _get_value(doc: Any, key: str) -> Any:
    if isinstance(doc, dict):
        if key == "band_gap" and key not in doc and "json_data" in doc:
            return doc["json_data"]["band_gap"]
        return doc.get(key)
    if key == "band_gap" and not hasattr(doc, key) and hasattr(doc, "json_data"):
        return doc.json_data["band_gap"]
    return getattr(doc, key)


def _as_composition(value: Any) -> Composition:
    if isinstance(value, Composition):
        return value
    return Composition(value)


def _as_structure(value: Any) -> Structure:
    if isinstance(value, Structure):
        return value
    return Structure.from_dict(value)


def _package_version(distribution: str) -> str | None:
    try:
        return version(distribution)
    except PackageNotFoundError:
        return None


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _builder_metadata(docs: Iterable[Any]) -> dict[str, Any] | None:
    for raw_doc in docs:
        doc = unwrap_mp_offline_row(raw_doc)
        try:
            payload = _get_value(doc, "json_data")
        except (AttributeError, KeyError):
            continue
        if isinstance(payload, Mapping) and isinstance(payload.get("builder_meta"), Mapping):
            return dict(payload["builder_meta"])
    return None


def default_mp_provenance_path(output: str | Path) -> Path:
    """Return the default sidecar path for one normalized MP dataset."""
    return Path(f"{output}.provenance.json")


def _write_dataset_with_provenance(
    df: pd.DataFrame,
    *,
    output: str | Path,
    provenance: dict[str, Any],
    provenance_path: str | Path | None,
) -> pd.DataFrame:
    output = Path(output)
    sidecar = (
        Path(provenance_path) if provenance_path is not None else default_mp_provenance_path(output)
    )
    df.attrs[MP_DATASET_PROVENANCE_ATTR] = provenance
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_pickle(output)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(
        json.dumps(provenance, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    return df


def _offline_database_path(client: Any, offline_db: str | Path | None) -> Path:
    if offline_db is not None:
        database = Path(offline_db).expanduser().resolve()
    else:
        engine = getattr(client, "engine", None)
        url = getattr(engine, "url", None)
        database_name = getattr(url, "database", None)
        if not database_name:
            raise ValueError("Cannot determine the mp_offline database path for provenance")
        database = Path(database_name).expanduser().resolve()
    if not database.is_file():
        raise FileNotFoundError(f"Materials Project offline database not found: {database}")
    return database


def normalize_mp_documents(docs: Iterable[Any], *, source: str = "mp") -> pd.DataFrame:
    """Convert Materials Project summary documents to the screening schema."""
    records = []
    for raw_doc in docs:
        doc = unwrap_mp_offline_row(raw_doc)
        material_id = str(_get_value(doc, "material_id"))
        composition = _as_composition(_get_value(doc, "composition"))
        structure = _as_structure(_get_value(doc, "structure"))
        reduced_composition = composition.get_reduced_composition_and_factor()[0]
        records.append(
            {
                "material_id": material_id,
                "formula": reduced_composition.reduced_formula,
                "composition": composition,
                "reduced_composition": reduced_composition,
                "nelems": len(composition),
                "band_gap": float(_get_value(doc, "band_gap")),
                "e_hull": float(_get_value(doc, "energy_above_hull")),
                "energy_above_hull": float(_get_value(doc, "energy_above_hull")),
                "structure": structure,
                "primitive_structure": structure.get_primitive_structure(),
                "source": source,
            }
        )
    if not records:
        return pd.DataFrame(
            columns=[
                "formula",
                "composition",
                "reduced_composition",
                "nelems",
                "band_gap",
                "e_hull",
                "energy_above_hull",
                "structure",
                "primitive_structure",
                "source",
            ]
        ).rename_axis("material_id")
    return pd.DataFrame.from_records(records).set_index("material_id")


def load_mp_dataset_offline(
    *,
    output: str | Path,
    max_e_hull: float = 0.01,
    offline_db: str | Path | None = None,
    database_reference: str | None = None,
    provenance_path: str | Path | None = None,
    offline_client_factory: Callable[..., Any] | None = None,
    material_summary_cls: Any | None = None,
) -> pd.DataFrame:
    """Load Materials Project summaries from ``mp_offline`` and write a pickle DataFrame."""
    if offline_client_factory is None or material_summary_cls is None:
        try:
            from mp_offline.client import MPOffline
            from mp_offline.model import MaterialSummary
        except ImportError as exc:  # pragma: no cover - depends on local optional package
            raise ImportError(
                "Offline MP loading requires mp_offline. Install the local mp-offline "
                "package or add it to PYTHONPATH."
            ) from exc

        offline_client_factory = offline_client_factory or MPOffline
        material_summary_cls = material_summary_cls or MaterialSummary

    client = (
        offline_client_factory(offline_db) if offline_db is not None else offline_client_factory()
    )
    database = _offline_database_path(client, offline_db)
    try:
        criteria = (
            material_summary_cls.energy_above_hull >= 0.0,
            material_summary_cls.energy_above_hull <= max_e_hull,
            material_summary_cls.deprecated.is_(False),
        )
    except (AttributeError, TypeError):
        criteria = (
            ("energy_above_hull>=", 0.0),
            ("energy_above_hull<=", max_e_hull),
            ("deprecated is", False),
        )
    docs = client.query_all(*criteria, project=MP_OFFLINE_PROJECT_FIELDS)

    df = normalize_mp_documents(docs, source="mp-offline")
    provenance = {
        "schema_version": MP_DATASET_PROVENANCE_SCHEMA_VERSION,
        "backend": "offline",
        "source": "mp-offline",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "row_count": len(df),
        "query": {
            "energy_above_hull_eV_per_atom": {"min": 0.0, "max": float(max_e_hull)},
            "deprecated": False,
        },
        "projected_fields": MP_OFFLINE_PROJECT_FIELDS,
        "database": {
            ("reference" if database_reference is not None else "path"): (
                database_reference if database_reference is not None else str(database)
            ),
            "size_bytes": database.stat().st_size,
            "sha256": _sha256_file(database),
            "sample_document_builder_meta": _builder_metadata(docs),
            "scope_warning": (
                "Offline summary snapshot; completeness is limited to this database SHA-256 "
                "and does not imply current online Materials Project coverage."
            ),
        },
        "packages": {
            "ss-screen": _package_version("ss-screen"),
            "mp-offline": _package_version("mp-offline"),
            "SQLAlchemy": _package_version("SQLAlchemy"),
            "pymatgen": _package_version("pymatgen"),
            "pandas": _package_version("pandas"),
        },
    }
    return _write_dataset_with_provenance(
        df,
        output=output,
        provenance=provenance,
        provenance_path=provenance_path,
    )


def load_mp_dataset_api(
    *,
    output: str | Path,
    max_e_hull: float = 0.01,
    provenance_path: str | Path | None = None,
    rester_factory: Callable[[], Any] | None = None,
) -> pd.DataFrame:
    """Fetch live Materials Project summaries and write a normalized pickle DataFrame."""
    if rester_factory is None:
        try:
            from mp_api.client import MPRester
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise ImportError(
                "Materials Project loading requires mp-api. Install `ss-screen[mp]`."
            ) from exc

        rester_factory = partial(MPRester, timeout=MP_API_REQUEST_TIMEOUT_SECONDS)

    with rester_factory() as rester:
        docs = []
        page = 1
        while True:
            for attempt in range(1, MP_API_PAGE_RETRIES + 1):
                try:
                    page_docs = rester.materials.summary.search(
                        energy_above_hull=(0, max_e_hull),
                        deprecated=False,
                        fields=MP_SUMMARY_FIELDS,
                        chunk_size=MP_API_CHUNK_SIZE,
                        num_chunks=1,
                        _page=page,
                        _sort_fields="material_id",
                    )
                    break
                except Exception:
                    if attempt == MP_API_PAGE_RETRIES:
                        raise
                    time.sleep(MP_API_RETRY_BACKOFF_SECONDS * attempt)
            docs.extend(page_docs)
            if len(page_docs) < MP_API_CHUNK_SIZE:
                break
            page += 1
        database_version = getattr(rester, "db_version", None)

    df = normalize_mp_documents(docs, source="mp-api")
    provenance = {
        "schema_version": MP_DATASET_PROVENANCE_SCHEMA_VERSION,
        "backend": "api",
        "source": "mp-api",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "row_count": len(df),
        "query": {
            "energy_above_hull_eV_per_atom": {"min": 0.0, "max": float(max_e_hull)},
            "deprecated": False,
        },
        "projected_fields": MP_SUMMARY_FIELDS,
        "request": {
            "chunk_size": MP_API_CHUNK_SIZE,
            "page_retries": MP_API_PAGE_RETRIES,
            "pagination": "explicit_pages",
            "retry_backoff_seconds": MP_API_RETRY_BACKOFF_SECONDS,
            "sort_fields": "material_id",
            "timeout_seconds": MP_API_REQUEST_TIMEOUT_SECONDS,
        },
        "database": {"version": database_version},
        "packages": {
            "ss-screen": _package_version("ss-screen"),
            "mp-api": _package_version("mp-api"),
            "pymatgen": _package_version("pymatgen"),
            "pandas": _package_version("pandas"),
        },
    }
    return _write_dataset_with_provenance(
        df,
        output=output,
        provenance=provenance,
        provenance_path=provenance_path,
    )


def load_mp_dataset(
    *,
    output: str | Path,
    max_e_hull: float = 0.01,
    backend: str = "offline",
    offline_db: str | Path | None = None,
    database_reference: str | None = None,
    provenance_path: str | Path | None = None,
    offline_client_factory: Callable[..., Any] | None = None,
    material_summary_cls: Any | None = None,
    rester_factory: Callable[[], Any] | None = None,
) -> pd.DataFrame:
    """Load Materials Project data using the selected backend."""
    if backend == "offline":
        return load_mp_dataset_offline(
            output=output,
            max_e_hull=max_e_hull,
            offline_db=offline_db,
            database_reference=database_reference,
            provenance_path=provenance_path,
            offline_client_factory=offline_client_factory,
            material_summary_cls=material_summary_cls,
        )
    if backend == "api":
        return load_mp_dataset_api(
            output=output,
            max_e_hull=max_e_hull,
            provenance_path=provenance_path,
            rester_factory=rester_factory,
        )
    raise ValueError(f"Unsupported MP backend: {backend}")


def write_mp_dataset(df: pd.DataFrame, output: str | Path) -> pd.DataFrame:
    """Write an already-normalized MP DataFrame and return it."""
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    df.to_pickle(output)
    return df
