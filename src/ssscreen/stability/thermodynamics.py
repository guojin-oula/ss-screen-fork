"""Mixing-enthalpy estimates from compatible Stage 7 relaxation records."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

MIXING_SCHEMA_VERSION = 1
ENERGY_BACKEND_FIELDS = ("name", "version", "model_sha256", "dtype")
ENERGY_SETTING_FIELDS = (
    "optimizer",
    "cell_mode",
    "fmax_ev_per_angstrom",
    "max_steps",
    "quality_control",
)
QUALITY_CONTROL_FIELDS = (
    "min_volume_ratio",
    "max_volume_ratio",
    "min_distance_angstrom",
)
REQUIRED_PAIR_COLUMNS = ("comp_a", "comp_b", "mp_id_a", "mp_id_b")
OUTPUT_COLUMNS = [
    "schema_version",
    "pair_index",
    "source_group_index",
    "mp_id_a",
    "mp_id_b",
    "comp_a",
    "comp_b",
    "target_fraction_b",
    "actual_fraction_b",
    "fraction_basis",
    "sqs_structure_id",
    "endmember_a_structure_id",
    "endmember_b_structure_id",
    "energy_sqs_per_atom_eV",
    "energy_endmember_a_per_atom_eV",
    "energy_endmember_b_per_atom_eV",
    "reference_energy_per_atom_eV",
    "mixing_enthalpy_eV_per_atom",
    "mixing_enthalpy_meV_per_atom",
    "mixing_signal",
    "backend_name",
    "backend_version",
    "model_name",
    "model_sha256",
    "dtype",
    "sqs_device",
    "endmember_a_device",
    "endmember_b_device",
    "energy_reference_sha256",
    "status",
    "usable_for_screening",
    "warnings",
    "error",
]


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


def _load_pairs(path: Path) -> pd.DataFrame:
    pairs = pd.read_csv(path)
    unnamed = [column for column in pairs.columns if str(column).startswith("Unnamed:")]
    if unnamed:
        pairs = pairs.drop(columns=unnamed)
    missing = [column for column in REQUIRED_PAIR_COLUMNS if column not in pairs.columns]
    if missing:
        raise ValueError(f"missing required pair columns: {', '.join(missing)}")
    return pairs.reset_index(drop=True)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON on relaxation-results line {line_number}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"relaxation-results line {line_number} is not a JSON object")
            structure_id = record.get("structure_id")
            if not isinstance(structure_id, str) or not structure_id:
                raise ValueError(f"relaxation-results line {line_number} has no structure_id")
            if structure_id in seen:
                raise ValueError(f"duplicate relaxation structure_id: {structure_id}")
            seen.add(structure_id)
            records.append(record)
    return records


def _energy_signature(record: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    backend = record.get("backend")
    settings = record.get("settings")
    if not isinstance(backend, dict) or not isinstance(settings, dict):
        return None, None
    if any(backend.get(field) in (None, "") for field in ENERGY_BACKEND_FIELDS):
        return None, None
    if any(field not in settings for field in ENERGY_SETTING_FIELDS):
        return None, None
    quality_control = settings.get("quality_control")
    if not isinstance(quality_control, dict) or any(
        field not in quality_control for field in QUALITY_CONTROL_FIELDS
    ):
        return None, None
    payload = {
        "backend": {field: backend[field] for field in ENERGY_BACKEND_FIELDS},
        "settings": settings,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest(), payload


def _finite_energy(record: dict[str, Any]) -> float | None:
    try:
        energy = float(record["energy_per_atom_eV"])
    except (KeyError, TypeError, ValueError):
        return None
    return energy if math.isfinite(energy) else None


def _is_usable(record: dict[str, Any]) -> bool:
    return (
        record.get("status") == "success"
        and record.get("usable_for_thermodynamics") is True
        and _finite_energy(record) is not None
    )


def _select_endmember(
    material_id: str,
    *,
    endmembers: dict[str, list[dict[str, Any]]],
    energy_signature: str,
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    candidates = endmembers.get(material_id, [])
    if not candidates:
        return None, "missing_endmember", f"no relaxed endmember record for {material_id}"
    usable = [record for record in candidates if _is_usable(record)]
    if not usable:
        return None, "unusable_endmember", f"no usable endmember energy for {material_id}"
    compatible = [record for record in usable if _energy_signature(record)[0] == energy_signature]
    if not compatible:
        return (
            None,
            "incompatible_provenance",
            f"endmember {material_id} was not relaxed with the SQS energy reference",
        )
    if len(compatible) > 1:
        return (
            None,
            "ambiguous_endmember",
            f"multiple compatible endmember records exist for {material_id}",
        )
    return compatible[0], None, None


def _fraction_b(record: dict[str, Any]) -> tuple[float | None, str | None, list[str], str | None]:
    warnings: list[str] = []
    target_raw = record.get("target_fraction_b")
    try:
        target = float(target_raw)
    except (TypeError, ValueError):
        return None, None, warnings, "SQS record has no valid target_fraction_b"

    basis = "actual"
    if record.get("actual_fraction_b") is not None:
        try:
            fraction = float(record["actual_fraction_b"])
        except (TypeError, ValueError):
            return None, None, warnings, "SQS record has an invalid actual_fraction_b"
    elif (
        record.get("replaced_sites") is not None
        and record.get("available_substitution_sites") is not None
    ):
        try:
            available = int(record["available_substitution_sites"])
            replaced = int(record["replaced_sites"])
        except (TypeError, ValueError):
            return None, None, warnings, "SQS record has invalid substitution-site counts"
        if available <= 0:
            return None, None, warnings, "available_substitution_sites must be positive"
        fraction = replaced / available
        basis = "site_counts"
    else:
        fraction = target
        basis = "target_fallback"
        warnings.append("actual fraction unavailable; target_fraction_b was used")

    if not math.isfinite(target) or not math.isfinite(fraction):
        return None, None, warnings, "SQS fraction is not finite"
    if not 0.0 <= target <= 1.0 or not 0.0 <= fraction <= 1.0:
        return None, None, warnings, "SQS fractions must be between 0 and 1"
    if not math.isclose(target, fraction, rel_tol=0.0, abs_tol=1e-12):
        warnings.append(
            f"actual_fraction_b={fraction:.12g} differs from target_fraction_b={target:.12g}"
        )
    return fraction, basis, warnings, None


def _base_row(sqs: dict[str, Any], pair_index: int | None) -> dict[str, Any]:
    row = {column: None for column in OUTPUT_COLUMNS}
    row.update(
        {
            "schema_version": MIXING_SCHEMA_VERSION,
            "pair_index": pair_index,
            "source_group_index": sqs.get("source_group_index"),
            "mp_id_a": sqs.get("mp_id_a"),
            "mp_id_b": sqs.get("mp_id_b"),
            "comp_a": sqs.get("comp_a"),
            "comp_b": sqs.get("comp_b"),
            "target_fraction_b": sqs.get("target_fraction_b"),
            "sqs_structure_id": sqs.get("structure_id"),
            "status": "invalid_sqs_metadata",
            "usable_for_screening": False,
            "warnings": "",
        }
    )
    backend = sqs.get("backend")
    if isinstance(backend, dict):
        row.update(
            {
                "backend_name": backend.get("name"),
                "backend_version": backend.get("version"),
                "model_name": backend.get("model_name"),
                "model_sha256": backend.get("model_sha256"),
                "dtype": backend.get("dtype"),
                "sqs_device": backend.get("device"),
            }
        )
    return row


def _failed_row(
    row: dict[str, Any], status: str, error: str, warnings: list[str]
) -> dict[str, Any]:
    row.update(
        {
            "status": status,
            "usable_for_screening": False,
            "warnings": "; ".join(warnings),
            "error": error,
        }
    )
    return row


def calculate_mixing_enthalpies(
    *,
    pairs_path: str | Path,
    relax_results_path: str | Path,
    output_path: str | Path,
    summary_path: str | Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Calculate per-SQS mixing enthalpies using compatible relaxed endmembers.

    The per-atom definition is ``E_sqs(x) - [(1-x) E_a + x E_b]``. Records are
    never silently discarded: unusable or incompatible inputs produce rows with
    an explicit non-success status and no mixing enthalpy.
    """
    pairs_path = Path(pairs_path)
    relax_results_path = Path(relax_results_path)
    output_path = Path(output_path)
    summary_path = Path(summary_path)
    pairs = _load_pairs(pairs_path)
    relaxation_records = _read_jsonl(relax_results_path)

    endmembers: dict[str, list[dict[str, Any]]] = {}
    sqs_records: list[dict[str, Any]] = []
    for record in relaxation_records:
        role = record.get("structure_role")
        if role == "endmember":
            material_id = record.get("material_id")
            if isinstance(material_id, str) and material_id:
                endmembers.setdefault(material_id, []).append(record)
        elif role == "sqs":
            sqs_records.append(record)

    rows: list[dict[str, Any]] = []
    for sqs in sqs_records:
        try:
            pair_index = int(sqs["pair_index"])
        except (KeyError, TypeError, ValueError):
            rows.append(
                _failed_row(
                    _base_row(sqs, None),
                    "invalid_sqs_metadata",
                    "SQS record has no valid pair_index",
                    [],
                )
            )
            continue

        row = _base_row(sqs, pair_index)
        if pair_index < 0 or pair_index >= len(pairs):
            rows.append(
                _failed_row(row, "pair_not_found", f"pair_index {pair_index} is out of range", [])
            )
            continue

        pair = pairs.iloc[pair_index]
        row.update(
            {
                "source_group_index": pair.get("source_group_index", row["source_group_index"]),
                "mp_id_a": str(pair["mp_id_a"]),
                "mp_id_b": str(pair["mp_id_b"]),
                "comp_a": str(pair["comp_a"]),
                "comp_b": str(pair["comp_b"]),
            }
        )
        for endpoint in ("a", "b"):
            sqs_id = sqs.get(f"mp_id_{endpoint}")
            if sqs_id is None or str(sqs_id) != row[f"mp_id_{endpoint}"]:
                rows.append(
                    _failed_row(
                        row,
                        "pair_metadata_mismatch",
                        f"SQS mp_id_{endpoint} does not match pair row {pair_index}",
                        [],
                    )
                )
                break
        else:
            if not _is_usable(sqs):
                rows.append(
                    _failed_row(
                        row,
                        "unusable_sqs",
                        "SQS relaxation is not successful and usable for thermodynamics",
                        [],
                    )
                )
                continue

            signature, _ = _energy_signature(sqs)
            if signature is None:
                rows.append(
                    _failed_row(
                        row,
                        "invalid_provenance",
                        "SQS record lacks a complete backend/settings energy reference",
                        [],
                    )
                )
                continue

            endpoint_a, status, error = _select_endmember(
                row["mp_id_a"], endmembers=endmembers, energy_signature=signature
            )
            if endpoint_a is None:
                rows.append(_failed_row(row, status or "missing_endmember", error or "", []))
                continue
            endpoint_b, status, error = _select_endmember(
                row["mp_id_b"], endmembers=endmembers, energy_signature=signature
            )
            if endpoint_b is None:
                rows.append(_failed_row(row, status or "missing_endmember", error or "", []))
                continue

            fraction, basis, warnings, fraction_error = _fraction_b(sqs)
            if fraction is None:
                rows.append(
                    _failed_row(
                        row,
                        "invalid_fraction",
                        fraction_error or "invalid SQS fraction",
                        warnings,
                    )
                )
                continue

            energy_sqs = _finite_energy(sqs)
            energy_a = _finite_energy(endpoint_a)
            energy_b = _finite_energy(endpoint_b)
            if energy_sqs is None or energy_a is None or energy_b is None:
                rows.append(
                    _failed_row(
                        row,
                        "invalid_energy",
                        "one or more per-atom energies are missing or non-finite",
                        warnings,
                    )
                )
                continue

            reference_energy = (1.0 - fraction) * energy_a + fraction * energy_b
            mixing_enthalpy = energy_sqs - reference_energy
            if mixing_enthalpy < 0.0:
                signal = "exothermic"
            elif mixing_enthalpy > 0.0:
                signal = "endothermic"
            else:
                signal = "neutral"
            endpoint_a_backend = endpoint_a["backend"]
            endpoint_b_backend = endpoint_b["backend"]
            row.update(
                {
                    "actual_fraction_b": fraction,
                    "fraction_basis": basis,
                    "endmember_a_structure_id": endpoint_a["structure_id"],
                    "endmember_b_structure_id": endpoint_b["structure_id"],
                    "energy_sqs_per_atom_eV": energy_sqs,
                    "energy_endmember_a_per_atom_eV": energy_a,
                    "energy_endmember_b_per_atom_eV": energy_b,
                    "reference_energy_per_atom_eV": reference_energy,
                    "mixing_enthalpy_eV_per_atom": mixing_enthalpy,
                    "mixing_enthalpy_meV_per_atom": mixing_enthalpy * 1000.0,
                    "mixing_signal": signal,
                    "endmember_a_device": endpoint_a_backend.get("device"),
                    "endmember_b_device": endpoint_b_backend.get("device"),
                    "energy_reference_sha256": signature,
                    "status": "success",
                    "usable_for_screening": True,
                    "warnings": "; ".join(warnings),
                    "error": None,
                }
            )
            rows.append(row)

    frame = pd.DataFrame.from_records(rows, columns=OUTPUT_COLUMNS)
    status_counts = Counter(str(status) for status in frame["status"])
    successful_pair_indices = sorted(
        {int(value) for value in frame.loc[frame["status"] == "success", "pair_index"]}
    )
    summary = {
        "schema_version": MIXING_SCHEMA_VERSION,
        "definition": "E_sqs(x) - [(1-x) E_a + x E_b] using per-atom energies",
        "pairs_path": str(pairs_path),
        "relax_results_path": str(relax_results_path),
        "output_path": str(output_path),
        "input_pair_count": int(len(pairs)),
        "relaxation_record_count": int(len(relaxation_records)),
        "sqs_record_count": int(len(sqs_records)),
        "endmember_material_count": int(len(endmembers)),
        "status_counts": dict(sorted(status_counts.items())),
        "success_count": int(status_counts.get("success", 0)),
        "failed_count": int(len(frame) - status_counts.get("success", 0)),
        "successful_pair_indices": successful_pair_indices,
        "missing_pair_indices": sorted(set(range(len(pairs))) - set(successful_pair_indices)),
        "target_fraction_fallback_count": int((frame["fraction_basis"] == "target_fallback").sum()),
        "provenance_policy": (
            "backend name/version, model SHA-256, dtype, and complete relaxation settings "
            "must match; compute device may differ"
        ),
    }
    _atomic_write_dataframe(frame, output_path)
    _atomic_write_text(summary_path, json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return frame, summary
