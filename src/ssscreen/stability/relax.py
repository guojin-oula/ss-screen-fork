"""Manifest-driven, resumable MLP relaxation and result persistence."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from monty.serialization import dumpfn, loadfn
from pymatgen.core import Structure

from ..config import MLPRelaxationSettings
from .mlp import RelaxationBackend, RelaxationOutcome

RESULT_SCHEMA_VERSION = 1
EV_PER_ANGSTROM3_TO_GPA = 160.21766208


@dataclass(frozen=True)
class RelaxationTask:
    """One stable structure task derived from an SQS manifest."""

    structure_id: str
    structure_role: str
    structure_path: Path
    metadata: dict[str, Any]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_name(value: object) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value)).strip("-.")
    return cleaned or "structure"


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


def _read_manifest(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON on manifest line {line_number}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"manifest line {line_number} is not a JSON object")
            records.append(record)
    return records


def _resolve_input_path(raw_path: str | Path, manifest_path: Path) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    relative_to_manifest = manifest_path.parent / path
    if relative_to_manifest.exists():
        return relative_to_manifest
    return path


def _metadata_from_record(record: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "pair_index",
        "mp_id_a",
        "mp_id_b",
        "comp_a",
        "comp_b",
        "target_fraction_b",
        "supercell",
        "seed",
        "generator",
        "substitution",
        "replaced_sites",
        "available_substitution_sites",
        "actual_fraction_b",
        "mp_entry_id",
        "reduced_formula",
        "chemical_system",
        "parent_chemical_systems",
        "mp_energy_above_hull_eV_per_atom",
        "mp_thermo_type",
        "mp_database_version",
        "mp_retrieved_at_utc",
        "source_atom_count",
        "calculation_atom_count",
    )
    return {key: record[key] for key in keys if key in record}


def _verify_declared_hash(record: dict[str, Any], *, key: str, actual: str, label: str) -> None:
    declared = record.get(key)
    if declared is not None and declared != actual:
        raise ValueError(
            f"{label} SHA-256 differs from manifest: declared={declared}, actual={actual}"
        )


def _structure_from_dataset(dataset: Any, material_id: str) -> Structure:
    if material_id not in dataset.index:
        raise ValueError(f"dataset is missing endpoint structure {material_id}")
    row = dataset.loc[material_id]
    for column in ("primitive_structure", "structure"):
        if column in row and isinstance(row[column], Structure):
            return row[column].copy()
    raise ValueError(f"dataset endpoint {material_id} has no pymatgen Structure")


def _endpoint_path(
    record: dict[str, Any],
    endpoint: str,
    *,
    manifest_path: Path,
    dataset: Any | None,
    output_dir: Path,
) -> Path:
    path_key = f"endpoint_{endpoint}_structure_path"
    if path_key in record:
        return _resolve_input_path(record[path_key], manifest_path)
    if dataset is None:
        raise ValueError(
            f"manifest has no {path_key}; provide --dataset for an older Stage 6 manifest"
        )
    material_id = str(record[f"mp_id_{endpoint}"])
    path = output_dir / "inputs" / "endmembers" / f"{_safe_name(material_id)}.json"
    if not path.exists():
        _atomic_write_structure(_structure_from_dataset(dataset, material_id), path)
    return path


def build_relaxation_tasks(
    *,
    manifest_path: str | Path,
    output_dir: str | Path,
    include_endmembers: bool = False,
    dataset_path: str | Path | None = None,
) -> list[RelaxationTask]:
    """Expand written SQS or competing-phase rows into de-duplicated tasks."""
    manifest_path = Path(manifest_path)
    output_dir = Path(output_dir)
    records = _read_manifest(manifest_path)
    dataset = None
    if include_endmembers and dataset_path is not None:
        import pandas as pd

        dataset = pd.read_pickle(dataset_path)

    tasks: list[RelaxationTask] = []
    seen: set[str] = set()
    for record in records:
        if record.get("status") != "written":
            continue
        if record.get("structure_role") == "competing_phase":
            if "structure_path" not in record:
                raise ValueError("written competing-phase manifest row has no structure_path")
            structure_path = _resolve_input_path(record["structure_path"], manifest_path)
            if not structure_path.is_file():
                raise FileNotFoundError(
                    f"competing-phase input structure does not exist: {structure_path}"
                )
            input_hash = _sha256_file(structure_path)
            _verify_declared_hash(
                record,
                key="structure_sha256",
                actual=input_hash,
                label="competing-phase input structure",
            )
            structure_id = record.get("structure_id")
            if not isinstance(structure_id, str) or not structure_id:
                raise ValueError("written competing-phase row has no structure_id")
            if structure_id in seen:
                continue
            tasks.append(
                RelaxationTask(
                    structure_id=structure_id,
                    structure_role="competing_phase",
                    structure_path=structure_path,
                    metadata=_metadata_from_record(record),
                )
            )
            seen.add(structure_id)
            continue
        if "structure_path" not in record:
            raise ValueError("written SQS manifest row has no structure_path")
        structure_path = _resolve_input_path(record["structure_path"], manifest_path)
        if not structure_path.is_file():
            raise FileNotFoundError(f"SQS input structure does not exist: {structure_path}")
        input_hash = _sha256_file(structure_path)
        _verify_declared_hash(
            record,
            key="structure_sha256",
            actual=input_hash,
            label="SQS input structure",
        )
        pair_index = int(record.get("pair_index", len(tasks)))
        fraction = float(record.get("target_fraction_b", 0.0))
        structure_id = f"sqs-pair-{pair_index:05d}-x-{fraction:.6f}-{input_hash[:12]}"
        if structure_id not in seen:
            tasks.append(
                RelaxationTask(
                    structure_id=structure_id,
                    structure_role="sqs",
                    structure_path=structure_path,
                    metadata=_metadata_from_record(record),
                )
            )
            seen.add(structure_id)

        if not include_endmembers:
            continue
        for endpoint in ("a", "b"):
            endpoint_path = _endpoint_path(
                record,
                endpoint,
                manifest_path=manifest_path,
                dataset=dataset,
                output_dir=output_dir,
            )
            if not endpoint_path.is_file():
                raise FileNotFoundError(f"endpoint input structure does not exist: {endpoint_path}")
            endpoint_hash = _sha256_file(endpoint_path)
            _verify_declared_hash(
                record,
                key=f"endpoint_{endpoint}_structure_sha256",
                actual=endpoint_hash,
                label=f"endpoint {endpoint.upper()} input structure",
            )
            material_id = str(record[f"mp_id_{endpoint}"])
            endpoint_id = f"endmember-{_safe_name(material_id)}-{endpoint_hash[:12]}"
            if endpoint_id in seen:
                continue
            tasks.append(
                RelaxationTask(
                    structure_id=endpoint_id,
                    structure_role="endmember",
                    structure_path=endpoint_path,
                    metadata={
                        "material_id": material_id,
                        "composition": str(record[f"comp_{endpoint}"]),
                    },
                )
            )
            seen.add(endpoint_id)
    return tasks


def _minimum_distance(structure: Structure) -> float | None:
    if len(structure) < 2:
        return None
    distances = np.asarray(structure.distance_matrix, dtype=float)
    distances[distances <= 1e-12] = np.inf
    minimum = float(np.min(distances))
    return minimum if math.isfinite(minimum) else None


def _validate_outcome(outcome: RelaxationOutcome, atom_count: int) -> tuple[np.ndarray, np.ndarray]:
    forces = np.asarray(outcome.forces_ev_per_angstrom, dtype=float)
    stress = np.asarray(outcome.stress_ev_per_angstrom3, dtype=float)
    if forces.shape != (atom_count, 3):
        raise ValueError(f"backend returned force shape {forces.shape}; expected {(atom_count, 3)}")
    if stress.shape != (3, 3):
        raise ValueError(f"backend returned stress shape {stress.shape}; expected (3, 3)")
    scalars = np.array(
        [outcome.initial_energy_total_ev, outcome.energy_total_ev, *forces.ravel(), *stress.ravel()]
    )
    if not np.all(np.isfinite(scalars)):
        raise ValueError("backend returned non-finite energy, force, or stress values")
    return forces, stress


def _quality_control(
    initial: Structure,
    final: Structure,
    *,
    settings: MLPRelaxationSettings,
) -> dict[str, Any]:
    warnings: list[str] = []
    same_composition = initial.composition == final.composition and len(initial) == len(final)
    if not same_composition:
        warnings.append("atom count or composition changed during relaxation")
    volume_ratio = float(final.volume / initial.volume)
    if not settings.min_volume_ratio <= volume_ratio <= settings.max_volume_ratio:
        warnings.append(
            f"final/initial volume ratio {volume_ratio:.6g} is outside "
            f"[{settings.min_volume_ratio}, {settings.max_volume_ratio}]"
        )
    min_distance = _minimum_distance(final)
    if min_distance is not None and min_distance < settings.min_distance:
        warnings.append(
            f"minimum interatomic distance {min_distance:.6g} Angstrom is below "
            f"{settings.min_distance} Angstrom"
        )
    return {
        "passed": not warnings,
        "warnings": warnings,
        "initial_volume_angstrom3": float(initial.volume),
        "final_volume_angstrom3": float(final.volume),
        "volume_ratio": volume_ratio,
        "minimum_distance_angstrom": min_distance,
    }


def _run_fingerprint(
    *, input_sha256: str, backend: dict[str, Any], settings: dict[str, Any]
) -> str:
    payload = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "input_sha256": input_sha256,
        "backend": backend,
        "settings": settings,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _base_record(
    task: RelaxationTask,
    *,
    input_sha256: str,
    backend: dict[str, Any],
    settings: dict[str, Any],
    fingerprint: str,
) -> dict[str, Any]:
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "structure_id": task.structure_id,
        "structure_role": task.structure_role,
        **task.metadata,
        "input_structure": {
            "path": str(task.structure_path),
            "sha256": input_sha256,
        },
        "backend": backend,
        "settings": settings,
        "run_fingerprint": fingerprint,
    }


def _load_existing_record(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    record = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        raise ValueError(f"existing result is not a JSON object: {path}")
    return record


def relax_manifest(
    *,
    manifest_path: str | Path,
    output_dir: str | Path,
    results_path: str | Path,
    backend: RelaxationBackend,
    include_endmembers: bool = False,
    dataset_path: str | Path | None = None,
    fmax: float = MLPRelaxationSettings.force_tolerance,
    max_steps: int = MLPRelaxationSettings.max_steps,
    relax_cell: bool = True,
    overwrite: bool = False,
    retry_failed: bool = False,
    limit: int | None = None,
    qc_settings: MLPRelaxationSettings | None = None,
) -> list[dict[str, Any]]:
    """Relax manifest structures and atomically persist complete per-task results."""
    if fmax <= 0:
        raise ValueError("fmax must be positive")
    if max_steps <= 0:
        raise ValueError("max_steps must be positive")
    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive")

    output_dir = Path(output_dir)
    results_path = Path(results_path)
    qc_settings = qc_settings or MLPRelaxationSettings(
        force_tolerance=fmax,
        max_steps=max_steps,
    )
    tasks = build_relaxation_tasks(
        manifest_path=manifest_path,
        output_dir=output_dir,
        include_endmembers=include_endmembers,
        dataset_path=dataset_path,
    )
    if limit is not None:
        tasks = tasks[:limit]

    backend_metadata = backend.metadata
    run_settings = {
        "optimizer": "FIRE",
        "cell_mode": "full" if relax_cell else "positions",
        "fmax_ev_per_angstrom": float(fmax),
        "max_steps": int(max_steps),
        "quality_control": {
            "min_volume_ratio": qc_settings.min_volume_ratio,
            "max_volume_ratio": qc_settings.max_volume_ratio,
            "min_distance_angstrom": qc_settings.min_distance,
        },
    }
    records: list[dict[str, Any]] = []
    for task in tasks:
        input_sha256 = _sha256_file(task.structure_path)
        fingerprint = _run_fingerprint(
            input_sha256=input_sha256,
            backend=backend_metadata,
            settings=run_settings,
        )
        record_path = output_dir / "records" / f"{task.structure_id}.json"
        existing = _load_existing_record(record_path)
        if existing is not None and not overwrite:
            if existing.get("run_fingerprint") != fingerprint:
                raise ValueError(
                    f"existing result settings differ for {task.structure_id}; use --overwrite"
                )
            if existing.get("status") != "failed" or not retry_failed:
                records.append(existing)
                continue

        started = time.perf_counter()
        base = _base_record(
            task,
            input_sha256=input_sha256,
            backend=backend_metadata,
            settings=run_settings,
            fingerprint=fingerprint,
        )
        try:
            initial = loadfn(task.structure_path)
            if not isinstance(initial, Structure):
                raise TypeError("input artifact is not a pymatgen Structure")
            outcome = backend.relax(
                initial.copy(),
                fmax=fmax,
                max_steps=max_steps,
                relax_cell=relax_cell,
            )
            forces, stress = _validate_outcome(outcome, len(initial))
            qc = _quality_control(initial, outcome.structure, settings=qc_settings)
            output_path = output_dir / "structures" / f"{task.structure_id}.json"
            _atomic_write_structure(outcome.structure, output_path)
            force_norms = np.linalg.norm(forces, axis=1)
            record = {
                **base,
                "output_structure": {
                    "path": str(output_path),
                    "sha256": _sha256_file(output_path),
                },
                "initial_energy_total_eV": float(outcome.initial_energy_total_ev),
                "energy_total_eV": float(outcome.energy_total_ev),
                "energy_per_atom_eV": float(outcome.energy_total_ev / len(initial)),
                "forces_eV_per_angstrom": forces.tolist(),
                "max_force_eV_per_angstrom": float(np.max(force_norms)),
                "rms_force_eV_per_angstrom": float(np.sqrt(np.mean(force_norms**2))),
                "stress_eV_per_angstrom3": stress.tolist(),
                "stress_GPa": (stress * EV_PER_ANGSTROM3_TO_GPA).tolist(),
                "stress_convention": "ASE Cartesian 3x3; tensile stress is positive",
                "steps": int(outcome.steps),
                "status": "success" if outcome.converged else "not_converged",
                "converged": bool(outcome.converged),
                "quality_control": qc,
                "usable_for_thermodynamics": bool(outcome.converged and qc["passed"]),
                "runtime_seconds": float(time.perf_counter() - started),
                "error": None,
            }
        except Exception as exc:
            record = {
                **base,
                "status": "failed",
                "converged": False,
                "usable_for_thermodynamics": False,
                "runtime_seconds": float(time.perf_counter() - started),
                "error": f"{type(exc).__name__}: {exc}"[:2000],
            }
        _atomic_write_text(record_path, json.dumps(record, indent=2, sort_keys=True) + "\n")
        records.append(record)

    lines = "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    _atomic_write_text(results_path, lines)
    return records
