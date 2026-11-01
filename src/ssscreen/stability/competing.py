"""Materials Project competing phases and same-MLIP convex-hull screening."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import signal
import tempfile
import threading
from collections import Counter
from collections.abc import Callable
from contextlib import contextmanager
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path
from typing import Any

import pandas as pd
from monty.serialization import dumpfn, loadfn
from pymatgen.analysis.phase_diagram import PhaseDiagram
from pymatgen.core import Composition, Structure
from pymatgen.entries.computed_entries import ComputedEntry

from ..config import CompetingPhaseSettings, MLPRelaxationSettings
from ..data.mp import unwrap_mp_offline_row
from .mlp import RelaxationBackend
from .relax import relax_manifest
from .thermodynamics import _energy_signature, _finite_energy, _is_usable

COMPETING_SCHEMA_VERSION = 1
HULL_SCHEMA_VERSION = 1
MP_SOURCE_BACKENDS = frozenset({"api", "offline"})
HULL_COLUMNS = [
    "schema_version",
    "structure_id",
    "pair_index",
    "composition",
    "chemical_system",
    "energy_total_eV",
    "energy_per_atom_eV",
    "energy_relative_to_competing_hull_eV_per_atom",
    "energy_above_hull_eV_per_atom",
    "candidate_lowers_hull",
    "decomposition",
    "hull_signal",
    "competing_manifest_count",
    "competing_usable_count",
    "competing_failed_count",
    "competing_set_complete",
    "mp_source_backend",
    "mp_source_scope",
    "mp_database_version",
    "mp_database_sha256",
    "backend_name",
    "backend_version",
    "model_name",
    "model_sha256",
    "dtype",
    "device",
    "energy_reference_sha256",
    "status",
    "usable_for_screening",
    "warnings",
    "error",
]
HULL_ENTRY_COLUMNS = [
    "schema_version",
    "target_structure_id",
    "chemical_system",
    "phase_structure_id",
    "phase_role",
    "phase_composition",
    "phase_energy_total_eV",
    "phase_energy_per_atom_eV",
    "phase_e_above_augmented_hull_eV_per_atom",
    "is_target",
]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_name(value: object) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value)).strip("-.")
    return cleaned or "phase"


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def _atomic_write_dataframe(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.stem}.", suffix=path.suffix or ".csv", dir=path.parent
    )
    os.close(descriptor)
    try:
        frame.to_csv(temporary, index=False)
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def _atomic_write_structure(structure: Structure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.stem}.", suffix=".json", dir=path.parent
    )
    os.close(descriptor)
    try:
        dumpfn(structure, temporary)
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def _read_jsonl(path: Path, *, label: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON on {label} line {line_number}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{label} line {line_number} is not a JSON object")
            records.append(record)
    return records


def _write_jsonl(records: list[dict[str, Any]], path: Path) -> None:
    _atomic_write_text(
        path,
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
    )


def _resolve_artifact_path(raw_path: str | Path, source_path: Path) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    candidate = source_path.parent / path
    return candidate if candidate.exists() else path


def _load_output_structure(record: dict[str, Any], source_path: Path) -> tuple[Structure, Path]:
    artifact = record.get("output_structure")
    if not isinstance(artifact, dict) or "path" not in artifact:
        raise ValueError("relaxation record has no output structure path")
    path = _resolve_artifact_path(artifact["path"], source_path)
    if not path.is_file():
        raise FileNotFoundError(f"relaxed structure does not exist: {path}")
    actual_hash = _sha256_file(path)
    declared_hash = artifact.get("sha256")
    if declared_hash is not None and declared_hash != actual_hash:
        raise ValueError("relaxed structure SHA-256 differs from result record")
    structure = loadfn(path)
    if not isinstance(structure, Structure):
        raise TypeError("relaxed artifact is not a pymatgen Structure")
    return structure, path


@contextmanager
def _temporary_mp_api_key(api_key: str):
    key = api_key.strip()
    if not key:
        raise ValueError("Materials Project API key must not be empty")
    previous = os.environ.get("MP_API_KEY")
    os.environ["MP_API_KEY"] = key
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("MP_API_KEY", None)
        else:
            os.environ["MP_API_KEY"] = previous


@contextmanager
def _wall_clock_timeout(seconds: float):
    """Bound one MP chemical-system query on POSIX main-thread execution."""
    if (
        not hasattr(signal, "setitimer")
        or threading.current_thread() is not threading.main_thread()
    ):
        yield
        return

    def raise_timeout(_signum, _frame):
        raise TimeoutError(f"Materials Project query exceeded {seconds:g} seconds")

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    signal.signal(signal.SIGALRM, raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)
        signal.signal(signal.SIGALRM, previous_handler)


def _candidate_systems(
    relax_results_path: Path,
    structure_ids: tuple[str, ...] | list[str],
) -> tuple[dict[str, list[str]], list[dict[str, str]]]:
    selected_ids = set(structure_ids)
    records = _read_jsonl(relax_results_path, label="relaxation-results")
    available_ids = {
        str(record.get("structure_id"))
        for record in records
        if record.get("structure_role") == "sqs"
    }
    missing = selected_ids - available_ids
    if missing:
        raise ValueError(f"relaxation results do not contain SQS IDs: {', '.join(sorted(missing))}")

    systems: dict[str, list[str]] = {}
    skipped: list[dict[str, str]] = []
    for record in records:
        if record.get("structure_role") != "sqs":
            continue
        structure_id = str(record.get("structure_id", ""))
        if selected_ids and structure_id not in selected_ids:
            continue
        if not _is_usable(record):
            skipped.append(
                {
                    "structure_id": structure_id,
                    "error": "candidate relaxation is not successful and usable for thermodynamics",
                }
            )
            continue
        try:
            structure, _ = _load_output_structure(record, relax_results_path)
            chemical_system = structure.composition.chemical_system
            systems.setdefault(chemical_system, []).append(structure_id)
        except Exception as exc:
            skipped.append(
                {"structure_id": structure_id, "error": f"{type(exc).__name__}: {exc}"[:2000]}
            )
    if not systems:
        raise ValueError("no usable SQS relaxation records matched the competing-phase selection")
    return systems, skipped


def _chemical_subsystems(chemical_system: str) -> tuple[str, ...]:
    elements = chemical_system.split("-")
    subsystems = {
        Composition({element: 1 for element in subset}).chemical_system
        for size in range(1, len(elements) + 1)
        for subset in combinations(elements, size)
    }
    return tuple(sorted(subsystems))


def _summary_value(row: Any, key: str) -> Any:
    document = unwrap_mp_offline_row(row)
    if isinstance(document, dict):
        return document.get(key)
    mapping = getattr(document, "_mapping", None)
    if mapping is not None and key in mapping:
        return mapping[key]
    return getattr(document, key)


def export_competing_phases(
    *,
    relax_results_path: str | Path,
    output_dir: str | Path,
    manifest_path: str | Path,
    report_path: str | Path,
    api_key: str | None = None,
    mp_backend: str = "api",
    offline_db: str | Path | None = None,
    structure_ids: tuple[str, ...] | list[str] = (),
    settings: CompetingPhaseSettings | None = None,
    mpr_factory: Callable[..., Any] | None = None,
    offline_client_factory: Callable[..., Any] | None = None,
    material_summary_cls: Any | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Discover MP structures from the API or an offline summary snapshot.

    Materials Project energies only select source structures. The final hull
    continues to use one compatible MLIP energy reference for every phase.
    """
    settings = settings or CompetingPhaseSettings()
    mp_backend = str(mp_backend).strip().lower()
    if mp_backend not in MP_SOURCE_BACKENDS:
        raise ValueError(f"unsupported Materials Project backend: {mp_backend}")
    if mp_backend == "api" and not str(api_key or "").strip():
        raise ValueError("Materials Project API backend requires a non-empty API key")
    if mp_backend == "offline" and offline_db is None:
        raise ValueError("offline Materials Project backend requires an explicit database path")
    if settings.max_mp_energy_above_hull < 0:
        raise ValueError("maximum MP energy above hull must be non-negative")
    if settings.max_competing_phase_atoms <= 0:
        raise ValueError("maximum competing-phase atom count must be positive")
    if settings.api_timeout_seconds <= 0:
        raise ValueError("Materials Project API timeout must be positive")

    relax_results_path = Path(relax_results_path)
    output_dir = Path(output_dir)
    manifest_path = Path(manifest_path)
    report_path = Path(report_path)
    systems, skipped_candidates = _candidate_systems(relax_results_path, structure_ids)
    for chemical_system in systems:
        if len(chemical_system.split("-")) > settings.max_query_elements:
            raise ValueError(
                f"chemical system {chemical_system} exceeds the query limit of "
                f"{settings.max_query_elements} elements"
            )

    records_by_entry: dict[str, dict[str, Any]] = {}
    fetched_count = 0
    duplicate_count = 0
    query_failures: list[dict[str, str]] = []
    database_version: str | None = None
    database_path: str | None = None
    database_sha256: str | None = None
    offline_package_version: str | None = None
    retrieved_at_utc = datetime.now(UTC).isoformat()
    source_scope = "live_thermo_query"
    source_warning: str | None = None
    thermo_type = settings.thermo_type
    thermo_type_filter_applied = True

    def record_query_failure(chemical_system: str, exc: Exception) -> None:
        error = f"{type(exc).__name__}: {exc}"[:2000]
        query_failures.append({"chemical_system": chemical_system, "error": error})
        failure_id = f"query-failure-{_safe_name(chemical_system)}"
        records_by_entry[failure_id] = {
            "schema_version": COMPETING_SCHEMA_VERSION,
            "structure_role": "competing_phase",
            "structure_id": failure_id,
            "mp_entry_id": failure_id,
            "reduced_formula": None,
            "chemical_system": chemical_system,
            "parent_chemical_systems": [chemical_system],
            "mp_energy_above_hull_eV_per_atom": None,
            "mp_source_backend": mp_backend,
            "mp_source_scope": source_scope,
            "mp_thermo_type": thermo_type,
            "mp_thermo_type_filter_applied": thermo_type_filter_applied,
            "mp_database_version": database_version,
            "mp_database_sha256": database_sha256,
            "mp_retrieved_at_utc": retrieved_at_utc,
            "mp_source_warning": source_warning,
            "status": "failed",
            "error": error,
        }

    def store_entry(
        *,
        entry_id: str,
        source_structure: Any,
        composition: Any,
        energy_above_hull: Any,
        parent_system: str,
    ) -> None:
        nonlocal duplicate_count
        if entry_id in records_by_entry:
            duplicate_count += 1
            parents = records_by_entry[entry_id]["parent_chemical_systems"]
            if parent_system not in parents:
                parents.append(parent_system)
                parents.sort()
            return
        if not isinstance(composition, Composition):
            composition = Composition(composition)
        base = {
            "schema_version": COMPETING_SCHEMA_VERSION,
            "structure_role": "competing_phase",
            "mp_entry_id": entry_id,
            "reduced_formula": composition.reduced_formula,
            "chemical_system": composition.chemical_system,
            "parent_chemical_systems": [parent_system],
            "mp_energy_above_hull_eV_per_atom": energy_above_hull,
            "mp_source_backend": mp_backend,
            "mp_source_scope": source_scope,
            "mp_thermo_type": thermo_type,
            "mp_thermo_type_filter_applied": thermo_type_filter_applied,
            "mp_database_version": database_version,
            "mp_database_sha256": database_sha256,
            "mp_retrieved_at_utc": retrieved_at_utc,
            "mp_source_warning": source_warning,
        }
        try:
            if isinstance(source_structure, dict):
                source_structure = Structure.from_dict(source_structure)
            if not isinstance(source_structure, Structure):
                raise TypeError("MP entry has no pymatgen Structure")
            primitive = source_structure.get_primitive_structure()
            if len(primitive) > settings.max_competing_phase_atoms:
                raise ValueError(
                    f"primitive phase has {len(primitive)} atoms, above configured "
                    f"maximum {settings.max_competing_phase_atoms}"
                )
            provisional = output_dir / "structures" / f"{_safe_name(entry_id)}.json"
            _atomic_write_structure(primitive, provisional)
            structure_hash = _sha256_file(provisional)
            structure_id = f"competing-{_safe_name(entry_id)}-{structure_hash[:12]}"
            final_path = output_dir / "structures" / f"{structure_id}.json"
            if final_path != provisional:
                provisional.replace(final_path)
            records_by_entry[entry_id] = {
                **base,
                "structure_id": structure_id,
                "source_atom_count": len(source_structure),
                "calculation_atom_count": len(primitive),
                "structure_path": str(final_path),
                "structure_sha256": structure_hash,
                "status": "written",
                "error": None,
            }
        except Exception as exc:
            records_by_entry[entry_id] = {
                **base,
                "structure_id": f"competing-{_safe_name(entry_id)}",
                "status": "skipped",
                "error": f"{type(exc).__name__}: {exc}"[:2000],
            }

    if mp_backend == "api":
        if mpr_factory is None:
            try:
                from mp_api.client import MPRester
            except ImportError as exc:
                raise ImportError(
                    "Materials Project competing phases require the optional `mp` dependencies; "
                    "install `ss-screen[mp]`"
                ) from exc
            import requests

            class TimeoutSession(requests.Session):
                def request(self, method, url, **kwargs):
                    kwargs.setdefault("timeout", settings.api_timeout_seconds)
                    return super().request(method, url, **kwargs)

            timeout_session = TimeoutSession()

            def mpr_factory(**kwargs):
                return MPRester(session=timeout_session, **kwargs)

        with _temporary_mp_api_key(str(api_key)):
            try:
                with _wall_clock_timeout(settings.api_timeout_seconds):
                    mpr_context = mpr_factory(mute_progress_bars=True)
            except Exception as exc:
                for chemical_system in sorted(systems):
                    record_query_failure(chemical_system, exc)
                mpr_context = None
            if mpr_context is not None:
                with mpr_context as mpr:
                    database_version = str(getattr(mpr, "db_version", None) or "unknown")
                    for chemical_system in sorted(systems):
                        try:
                            with _wall_clock_timeout(settings.api_timeout_seconds):
                                entries = mpr.get_entries_in_chemsys(
                                    chemical_system.split("-"),
                                    property_data=["energy_above_hull"],
                                    additional_criteria={
                                        "thermo_types": [settings.thermo_type],
                                        "energy_above_hull": (
                                            0.0,
                                            settings.max_mp_energy_above_hull,
                                        ),
                                    },
                                )
                        except Exception as exc:
                            record_query_failure(chemical_system, exc)
                            continue
                        for entry in entries:
                            fetched_count += 1
                            entry_id = str(entry.entry_id or f"anonymous-{fetched_count}")
                            store_entry(
                                entry_id=entry_id,
                                source_structure=entry.structure,
                                composition=entry.composition,
                                energy_above_hull=entry.data.get("energy_above_hull"),
                                parent_system=chemical_system,
                            )
    else:
        database = Path(offline_db).expanduser().resolve()
        if not database.is_file():
            raise FileNotFoundError(f"mp_offline database does not exist: {database}")
        database_path = str(database)
        database_sha256 = _sha256_file(database)
        database_version = f"offline-sha256-{database_sha256[:16]}"
        source_scope = "offline_summary_snapshot"
        source_warning = (
            "competition set is complete only relative to this offline summary snapshot; "
            "newer Materials Project phases may be absent"
        )
        thermo_type = None
        thermo_type_filter_applied = False
        if offline_client_factory is None or material_summary_cls is None:
            try:
                from mp_offline import __version__ as mp_offline_version
                from mp_offline.client import MPOffline
                from mp_offline.model import MaterialSummary
            except ImportError as exc:
                raise ImportError(
                    "Offline competing phases require the separately installed mp_offline "
                    "package and its SQLAlchemy dependency"
                ) from exc
            offline_package_version = mp_offline_version
            offline_client_factory = offline_client_factory or MPOffline
            material_summary_cls = material_summary_cls or MaterialSummary
        else:
            offline_package_version = "injected-test-client"

        client = offline_client_factory(database)
        projection = [
            "material_id",
            "structure",
            "composition",
            "chemsys",
            "formula_pretty",
            "nsites",
            "energy_above_hull",
        ]
        try:
            for chemical_system in sorted(systems):
                try:
                    rows = client.query_all(
                        material_summary_cls.chemsys.in_(_chemical_subsystems(chemical_system)),
                        material_summary_cls.energy_above_hull >= 0.0,
                        material_summary_cls.energy_above_hull <= settings.max_mp_energy_above_hull,
                        material_summary_cls.deprecated.is_(False),
                        project=projection,
                    )
                except Exception as exc:
                    record_query_failure(chemical_system, exc)
                    continue
                for row in rows:
                    fetched_count += 1
                    entry_id = str(
                        _summary_value(row, "material_id") or f"anonymous-{fetched_count}"
                    )
                    source_structure = _summary_value(row, "structure")
                    composition = _summary_value(row, "composition")
                    if composition is None:
                        composition = (
                            source_structure.composition
                            if isinstance(source_structure, Structure)
                            else Structure.from_dict(source_structure).composition
                        )
                    store_entry(
                        entry_id=entry_id,
                        source_structure=source_structure,
                        composition=composition,
                        energy_above_hull=_summary_value(row, "energy_above_hull"),
                        parent_system=chemical_system,
                    )
        finally:
            engine = getattr(client, "engine", None)
            if engine is not None and hasattr(engine, "dispose"):
                engine.dispose()

    records = sorted(records_by_entry.values(), key=lambda record: record["mp_entry_id"])
    _write_jsonl(records, manifest_path)
    status_counts = Counter(str(record["status"]) for record in records)
    report = {
        "schema_version": COMPETING_SCHEMA_VERSION,
        "relax_results_path": str(relax_results_path),
        "manifest_path": str(manifest_path),
        "output_dir": str(output_dir),
        "mp_source_backend": mp_backend,
        "mp_source_scope": source_scope,
        "mp_database_version": database_version,
        "mp_database_path": database_path,
        "mp_database_sha256": database_sha256,
        "mp_offline_package_version": offline_package_version,
        "mp_retrieved_at_utc": retrieved_at_utc,
        "mp_source_warning": source_warning,
        "mp_thermo_type_filter_applied": thermo_type_filter_applied,
        "chemical_systems": sorted(systems),
        "candidate_structure_ids_by_system": systems,
        "candidate_skip_count": len(skipped_candidates),
        "candidate_skips": skipped_candidates,
        "query_failure_count": len(query_failures),
        "query_failures": query_failures,
        "fetched_entry_count": fetched_count,
        "unique_entry_count": len(records),
        "deduplicated_entry_count": duplicate_count,
        "substituted_entry_count": 0,
        "status_counts": dict(sorted(status_counts.items())),
        "settings": {
            "thermo_type": thermo_type,
            "max_mp_energy_above_hull_eV_per_atom": settings.max_mp_energy_above_hull,
            "max_competing_phase_atoms": settings.max_competing_phase_atoms,
            "api_timeout_seconds": (settings.api_timeout_seconds if mp_backend == "api" else None),
        },
        "energy_policy": (
            "Materials Project energies select structures only; final hull energies must all "
            "come from one compatible MLIP relaxation reference"
        ),
        "api_key_persisted": False,
        "scientific_scope": (
            "online thermo query" if mp_backend == "api" else "offline summary snapshot"
        ),
    }
    _atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
    return records, report


def relax_competing_phases(
    *,
    manifest_path: str | Path,
    output_dir: str | Path,
    results_path: str | Path,
    backend: RelaxationBackend,
    fmax: float = MLPRelaxationSettings.force_tolerance,
    max_steps: int = MLPRelaxationSettings.max_steps,
    relax_cell: bool = True,
    overwrite: bool = False,
    retry_failed: bool = False,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Relax exported MP phases with the standard Stage 7 result contract."""
    return relax_manifest(
        manifest_path=manifest_path,
        output_dir=output_dir,
        results_path=results_path,
        backend=backend,
        fmax=fmax,
        max_steps=max_steps,
        relax_cell=relax_cell,
        overwrite=overwrite,
        retry_failed=retry_failed,
        limit=limit,
    )


def _elements_subset(composition: Composition, parent_system: str) -> bool:
    return {str(element) for element in composition.elements} <= set(parent_system.split("-"))


def _computed_entry(
    record: dict[str, Any],
    *,
    source_path: Path,
) -> tuple[ComputedEntry, Structure]:
    structure, _ = _load_output_structure(record, source_path)
    try:
        energy_total = float(record["energy_total_eV"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("relaxation record has no finite total energy") from exc
    if not math.isfinite(energy_total):
        raise ValueError("relaxation record has no finite total energy")
    return (
        ComputedEntry(
            structure.composition,
            energy_total,
            entry_id=str(record["structure_id"]),
        ),
        structure,
    )


def _decomposition_payload(decomposition: dict[ComputedEntry, float]) -> str:
    payload = {
        str(entry.entry_id): {
            "formula": entry.composition.reduced_formula,
            "fraction": float(fraction),
        }
        for entry, fraction in decomposition.items()
    }
    return json.dumps(payload, sort_keys=True)


def _failed_hull_row(
    record: dict[str, Any],
    *,
    status: str,
    error: str,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    row = {column: None for column in HULL_COLUMNS}
    backend = record.get("backend") if isinstance(record.get("backend"), dict) else {}
    row.update(
        {
            "schema_version": HULL_SCHEMA_VERSION,
            "structure_id": record.get("structure_id"),
            "pair_index": record.get("pair_index"),
            "backend_name": backend.get("name"),
            "backend_version": backend.get("version"),
            "model_name": backend.get("model_name"),
            "model_sha256": backend.get("model_sha256"),
            "dtype": backend.get("dtype"),
            "device": backend.get("device"),
            "status": status,
            "usable_for_screening": False,
            "warnings": "; ".join(warnings or []),
            "error": error,
        }
    )
    return row


def collect_convex_hulls(
    *,
    candidate_relax_results_path: str | Path,
    competing_manifest_path: str | Path,
    competing_relax_results_path: str | Path,
    output_path: str | Path,
    entries_output_path: str | Path,
    summary_path: str | Path,
    structure_ids: tuple[str, ...] | list[str] = (),
    screening_cutoff: float = CompetingPhaseSettings.screening_cutoff_ev_per_atom,
    numerical_tolerance: float = CompetingPhaseSettings.numerical_tolerance_ev_per_atom,
    allow_incomplete: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Compare each SQS against a complete same-MLIP competing-phase hull."""
    if screening_cutoff < 0:
        raise ValueError("hull screening cutoff must be non-negative")
    if numerical_tolerance < 0:
        raise ValueError("hull numerical tolerance must be non-negative")

    candidate_path = Path(candidate_relax_results_path)
    manifest_path = Path(competing_manifest_path)
    competing_path = Path(competing_relax_results_path)
    selected_ids = set(structure_ids)
    candidate_records = _read_jsonl(candidate_path, label="candidate relaxation-results")
    manifest_records = _read_jsonl(manifest_path, label="competing manifest")
    competing_records = _read_jsonl(competing_path, label="competing relaxation-results")
    competing_by_id = {
        str(record.get("structure_id")): record
        for record in competing_records
        if record.get("structure_id")
    }

    available_sqs = {
        str(record.get("structure_id"))
        for record in candidate_records
        if record.get("structure_role") == "sqs"
    }
    missing = selected_ids - available_sqs
    if missing:
        raise ValueError(
            f"candidate relaxation results do not contain: {', '.join(sorted(missing))}"
        )

    rows: list[dict[str, Any]] = []
    phase_rows: list[dict[str, Any]] = []
    for target in candidate_records:
        if target.get("structure_role") != "sqs":
            continue
        target_id = str(target.get("structure_id", ""))
        if selected_ids and target_id not in selected_ids:
            continue
        if not _is_usable(target):
            rows.append(
                _failed_hull_row(
                    target,
                    status="unusable_candidate",
                    error="candidate relaxation is not successful and usable for thermodynamics",
                )
            )
            continue
        signature, _ = _energy_signature(target)
        if signature is None:
            rows.append(
                _failed_hull_row(
                    target,
                    status="invalid_provenance",
                    error="candidate lacks a complete backend/settings energy reference",
                )
            )
            continue

        try:
            target_entry, target_structure = _computed_entry(target, source_path=candidate_path)
        except Exception as exc:
            rows.append(
                _failed_hull_row(
                    target,
                    status="invalid_candidate",
                    error=f"{type(exc).__name__}: {exc}"[:2000],
                )
            )
            continue
        chemical_system = target_structure.composition.chemical_system
        expected_manifest = [
            record
            for record in manifest_records
            if chemical_system in record.get("parent_chemical_systems", [])
        ]
        failures: list[str] = []
        source_warnings = sorted(
            {
                str(record["mp_source_warning"])
                for record in expected_manifest
                if record.get("mp_source_warning")
            }
        )
        source_metadata: dict[str, Any] = {}
        source_conflicts: list[str] = []
        for field in (
            "mp_source_backend",
            "mp_source_scope",
            "mp_database_version",
            "mp_database_sha256",
        ):
            values = {
                str(record[field])
                for record in expected_manifest
                if record.get(field) not in (None, "")
            }
            if len(values) > 1:
                source_conflicts.append(f"competing manifest mixes {field} values")
            source_metadata[field] = next(iter(values), None)
        if source_conflicts:
            row = _failed_hull_row(
                target,
                status="incompatible_competing_sources",
                error="; ".join(source_conflicts),
                warnings=source_warnings,
            )
            row.update(
                {
                    "composition": target_structure.composition.reduced_formula,
                    "chemical_system": chemical_system,
                    "competing_manifest_count": len(expected_manifest),
                    "competing_usable_count": 0,
                    "competing_failed_count": len(source_conflicts),
                    "competing_set_complete": False,
                    **source_metadata,
                    "energy_reference_sha256": signature,
                }
            )
            rows.append(row)
            continue
        reference: list[tuple[ComputedEntry, str, dict[str, Any]]] = []
        for manifest in expected_manifest:
            phase_id = str(manifest.get("structure_id", ""))
            if manifest.get("status") != "written":
                failures.append(f"{phase_id}: {manifest.get('error', 'MP phase was skipped')}")
                continue
            result = competing_by_id.get(phase_id)
            if result is None:
                failures.append(f"{phase_id}: no relaxation result")
                continue
            if not _is_usable(result):
                failures.append(f"{phase_id}: relaxation is not usable")
                continue
            if _energy_signature(result)[0] != signature:
                failures.append(f"{phase_id}: incompatible energy provenance")
                continue
            try:
                entry, _ = _computed_entry(result, source_path=competing_path)
                reference.append((entry, "competing_phase", result))
            except Exception as exc:
                failures.append(f"{phase_id}: {type(exc).__name__}: {exc}")

        for candidate in candidate_records:
            candidate_id = str(candidate.get("structure_id", ""))
            if candidate_id == target_id or not _is_usable(candidate):
                continue
            if _energy_signature(candidate)[0] != signature:
                continue
            try:
                entry, structure = _computed_entry(candidate, source_path=candidate_path)
            except Exception:
                continue
            if _elements_subset(structure.composition, chemical_system):
                reference.append((entry, str(candidate.get("structure_role")), candidate))

        complete = not failures
        if failures and not allow_incomplete:
            row = _failed_hull_row(
                target,
                status="incomplete_competing_set",
                error="one or more fetched competing phases are missing or unusable",
                warnings=[*source_warnings, *failures[:20]],
            )
            row.update(
                {
                    "composition": target_structure.composition.reduced_formula,
                    "chemical_system": chemical_system,
                    "competing_manifest_count": len(expected_manifest),
                    "competing_usable_count": sum(
                        role == "competing_phase" for _, role, _ in reference
                    ),
                    "competing_failed_count": len(failures),
                    "competing_set_complete": False,
                    **source_metadata,
                    "energy_reference_sha256": signature,
                }
            )
            rows.append(row)
            continue

        pure_elements = {
            str(entry.composition.elements[0])
            for entry, _, _ in reference
            if len(entry.composition.elements) == 1
        }
        missing_elements = sorted(set(chemical_system.split("-")) - pure_elements)
        if missing_elements:
            rows.append(
                _failed_hull_row(
                    target,
                    status="missing_elemental_reference",
                    error=f"missing relaxed elemental references: {', '.join(missing_elements)}",
                    warnings=[*source_warnings, *failures[:20]],
                )
            )
            continue

        try:
            reference_entries = [entry for entry, _, _ in reference]
            diagram = PhaseDiagram(reference_entries)
            decomposition, relative = diagram.get_decomp_and_e_above_hull(
                target_entry,
                allow_negative=True,
                check_stable=False,
            )
            if decomposition is None or relative is None:
                raise ValueError("pymatgen did not return a decomposition")
            relative = float(relative)
            above_hull = max(relative, 0.0)
            if relative <= numerical_tolerance:
                signal = "stable"
            elif above_hull <= screening_cutoff:
                signal = "metastable_within_cutoff"
            else:
                signal = "unstable"

            backend = target["backend"]
            warnings = [*source_warnings, *failures[:20]]
            status = "success" if complete else "uncertain_incomplete_competing_set"
            row = {
                "schema_version": HULL_SCHEMA_VERSION,
                "structure_id": target_id,
                "pair_index": target.get("pair_index"),
                "composition": target_structure.composition.reduced_formula,
                "chemical_system": chemical_system,
                "energy_total_eV": float(target["energy_total_eV"]),
                "energy_per_atom_eV": _finite_energy(target),
                "energy_relative_to_competing_hull_eV_per_atom": relative,
                "energy_above_hull_eV_per_atom": above_hull,
                "candidate_lowers_hull": relative < -numerical_tolerance,
                "decomposition": _decomposition_payload(decomposition),
                "hull_signal": signal,
                "competing_manifest_count": len(expected_manifest),
                "competing_usable_count": sum(
                    role == "competing_phase" for _, role, _ in reference
                ),
                "competing_failed_count": len(failures),
                "competing_set_complete": complete,
                **source_metadata,
                "backend_name": backend.get("name"),
                "backend_version": backend.get("version"),
                "model_name": backend.get("model_name"),
                "model_sha256": backend.get("model_sha256"),
                "dtype": backend.get("dtype"),
                "device": backend.get("device"),
                "energy_reference_sha256": signature,
                "status": status,
                "usable_for_screening": complete,
                "warnings": "; ".join(warnings),
                "error": None,
            }
            rows.append(row)

            augmented = PhaseDiagram([*reference_entries, target_entry])
            for entry, role, _record in [*reference, (target_entry, "sqs", target)]:
                phase_rows.append(
                    {
                        "schema_version": HULL_SCHEMA_VERSION,
                        "target_structure_id": target_id,
                        "chemical_system": chemical_system,
                        "phase_structure_id": str(entry.entry_id),
                        "phase_role": role,
                        "phase_composition": entry.composition.reduced_formula,
                        "phase_energy_total_eV": float(entry.energy),
                        "phase_energy_per_atom_eV": float(entry.energy_per_atom),
                        "phase_e_above_augmented_hull_eV_per_atom": float(
                            augmented.get_e_above_hull(entry)
                        ),
                        "is_target": entry.entry_id == target_entry.entry_id,
                    }
                )
        except Exception as exc:
            rows.append(
                _failed_hull_row(
                    target,
                    status="hull_failed",
                    error=f"{type(exc).__name__}: {exc}"[:2000],
                    warnings=[*source_warnings, *failures[:20]],
                )
            )

    if not rows:
        raise ValueError("no SQS candidate records matched the convex-hull selection")
    frame = pd.DataFrame(rows, columns=HULL_COLUMNS)
    entries_frame = pd.DataFrame(phase_rows, columns=HULL_ENTRY_COLUMNS)
    status_counts = Counter(str(value) for value in frame["status"])
    signal_counts = Counter(str(value) for value in frame["hull_signal"].dropna())
    summary = {
        "schema_version": HULL_SCHEMA_VERSION,
        "candidate_relax_results_path": str(candidate_path),
        "competing_manifest_path": str(manifest_path),
        "competing_relax_results_path": str(competing_path),
        "output_path": str(output_path),
        "entries_output_path": str(entries_output_path),
        "candidate_count": len(frame),
        "status_counts": dict(sorted(status_counts.items())),
        "hull_signal_counts": dict(sorted(signal_counts.items())),
        "mp_source_backends": sorted(
            {
                str(record["mp_source_backend"])
                for record in manifest_records
                if record.get("mp_source_backend")
            }
        ),
        "mp_source_scopes": sorted(
            {
                str(record["mp_source_scope"])
                for record in manifest_records
                if record.get("mp_source_scope")
            }
        ),
        "mp_database_versions": sorted(
            {
                str(record["mp_database_version"])
                for record in manifest_records
                if record.get("mp_database_version")
            }
        ),
        "mp_database_sha256_values": sorted(
            {
                str(record["mp_database_sha256"])
                for record in manifest_records
                if record.get("mp_database_sha256")
            }
        ),
        "success_count": int(status_counts.get("success", 0)),
        "uncertain_count": int(status_counts.get("uncertain_incomplete_competing_set", 0)),
        "failed_count": int(
            len(frame)
            - status_counts.get("success", 0)
            - status_counts.get("uncertain_incomplete_competing_set", 0)
        ),
        "settings": {
            "screening_cutoff_eV_per_atom": screening_cutoff,
            "numerical_tolerance_eV_per_atom": numerical_tolerance,
            "allow_incomplete": allow_incomplete,
        },
        "energy_policy": (
            "candidate and competing entries must share backend name/version, model SHA-256, "
            "dtype, and complete relaxation settings; compute device may differ"
        ),
        "scientific_scope": (
            "0 K same-MLIP potential-energy convex hull; excludes vibrational/configurational "
            "free energies and requires DFT validation for final claims"
        ),
    }
    _atomic_write_dataframe(frame, Path(output_path))
    _atomic_write_dataframe(entries_frame, Path(entries_output_path))
    _atomic_write_text(Path(summary_path), json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return frame, entries_frame, summary


def run_phase_diagram_pipeline(
    *,
    candidate_relax_results_path: str | Path,
    output_dir: str | Path,
    api_key: str | None = None,
    mp_backend: str = "api",
    offline_db: str | Path | None = None,
    backend: RelaxationBackend,
    settings: CompetingPhaseSettings | None = None,
    structure_ids: tuple[str, ...] | list[str] = (),
    fmax: float = MLPRelaxationSettings.force_tolerance,
    max_steps: int = MLPRelaxationSettings.max_steps,
    relax_cell: bool = True,
    allow_incomplete: bool = False,
    overwrite: bool = False,
    retry_failed: bool = False,
    mpr_factory: Callable[..., Any] | None = None,
    offline_client_factory: Callable[..., Any] | None = None,
    material_summary_cls: Any | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Run MP export, same-MLIP relaxation, and convex-hull collection end to end."""
    settings = settings or CompetingPhaseSettings()
    output_dir = Path(output_dir)
    manifest = output_dir / "competing_phases.jsonl"
    export_report = output_dir / "competing_export_summary.json"
    competing_results = output_dir / "competing_relaxation_results.jsonl"
    export_competing_phases(
        relax_results_path=candidate_relax_results_path,
        output_dir=output_dir / "inputs",
        manifest_path=manifest,
        report_path=export_report,
        api_key=api_key,
        mp_backend=mp_backend,
        offline_db=offline_db,
        structure_ids=structure_ids,
        settings=settings,
        mpr_factory=mpr_factory,
        offline_client_factory=offline_client_factory,
        material_summary_cls=material_summary_cls,
    )
    relax_competing_phases(
        manifest_path=manifest,
        output_dir=output_dir / "relaxation",
        results_path=competing_results,
        backend=backend,
        fmax=fmax,
        max_steps=max_steps,
        relax_cell=relax_cell,
        overwrite=overwrite,
        retry_failed=retry_failed,
    )
    return collect_convex_hulls(
        candidate_relax_results_path=candidate_relax_results_path,
        competing_manifest_path=manifest,
        competing_relax_results_path=competing_results,
        output_path=output_dir / "phase_stability.csv",
        entries_output_path=output_dir / "hull_entries.csv",
        summary_path=output_dir / "phase_stability_summary.json",
        structure_ids=structure_ids,
        screening_cutoff=settings.screening_cutoff_ev_per_atom,
        numerical_tolerance=settings.numerical_tolerance_ev_per_atom,
        allow_incomplete=allow_incomplete,
    )
