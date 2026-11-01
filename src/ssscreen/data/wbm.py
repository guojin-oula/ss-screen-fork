"""WBM dataset normalization helpers."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd
from pymatgen.io.ase import AseAtomsAdaptor


def _info_value(info: dict[str, Any], key: str, default=None):
    value = info.get(key, default)
    return value.item() if hasattr(value, "item") else value


def _material_id(info: dict[str, Any], index: int) -> str:
    if "material_id" in info:
        return str(info["material_id"])
    if "WBM_idx" in info:
        return f"wbm-{_info_value(info, 'WBM_idx')}"
    return f"wbm-{index}"


def _summary_metadata(summary: pd.DataFrame | None, index: int) -> dict:
    if summary is None or index >= len(summary):
        return {}
    row = summary.iloc[index]
    return {
        str(key): row[key].item() if hasattr(row[key], "item") else row[key] for key in row.index
    }


_MISSING = object()


def _first_present(mapping: dict[str, Any], *keys: str, default: Any = _MISSING) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return default


def _strict_nonnegative_number(value: Any, *, field: str, index: int) -> float:
    if value is _MISSING or value is None or pd.isna(value):
        raise ValueError(f"WBM record {index} is missing required {field}")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"WBM record {index} has non-numeric {field}") from error
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"WBM record {index} has invalid {field}; expected a finite value >= 0")
    return number


def _identity_text(value: Any) -> str:
    value = value.item() if hasattr(value, "item") else value
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def load_wbm_dataset(
    *,
    xyz_path: str | Path,
    output: str | Path,
    summary_path: str | Path | None = None,
    strict: bool = False,
) -> pd.DataFrame:
    """Load WBM extxyz structures into the normalized screening DataFrame schema."""
    try:
        from ase.io import read
    except ImportError as exc:
        raise ImportError(
            "The optional 'ase' dependency is required for `ss-screen dataset wbm`. "
            "Install it with `pip install -e '.[wbm]'`."
        ) from exc

    atoms_list = read(str(xyz_path), index=":")
    if not isinstance(atoms_list, list):
        atoms_list = [atoms_list]
    summary = (
        pd.read_csv(summary_path, sep=None, engine="python") if summary_path is not None else None
    )
    if strict and not atoms_list:
        raise ValueError("WBM extxyz contains no structures")
    if strict and summary is not None and len(summary) != len(atoms_list):
        raise ValueError(
            "WBM summary row count does not match the extxyz structure count: "
            f"{len(summary)} != {len(atoms_list)}"
        )
    records = []
    material_ids: set[str] = set()
    adaptor = AseAtomsAdaptor()
    for index, atoms in enumerate(atoms_list):
        info = dict(atoms.info)
        structure = adaptor.get_structure(atoms)
        composition = structure.composition
        reduced = composition.get_reduced_composition_and_factor()[0]
        metadata = _summary_metadata(summary, index)
        material_id = _material_id(info, index)
        if strict and material_id in material_ids:
            raise ValueError(f"WBM material_id is duplicated: {material_id}")
        if strict and "material_id" in metadata and str(metadata["material_id"]) != material_id:
            raise ValueError(
                f"WBM summary material_id does not match extxyz record {index}: "
                f"{metadata['material_id']} != {material_id}"
            )
        if strict and "WBM_idx" in metadata:
            expected_index = _info_value(info, "WBM_idx", index)
            if _identity_text(metadata["WBM_idx"]) != _identity_text(expected_index):
                raise ValueError(
                    f"WBM summary WBM_idx does not match extxyz record {index}: "
                    f"{metadata['WBM_idx']} != {expected_index}"
                )
        gap_value = _info_value(
            info,
            "WBM_gap",
            _first_present(metadata, "band_gap", "gap", "WBM_gap", default=_MISSING),
        )
        hull_value = _info_value(
            info,
            "WBM_e_hull",
            _first_present(
                metadata,
                "e_hull",
                "energy_above_hull",
                "WBM_e_hull",
                default=_MISSING,
            ),
        )
        if strict:
            band_gap = _strict_nonnegative_number(gap_value, field="band_gap", index=index)
            e_hull = _strict_nonnegative_number(hull_value, field="e_hull", index=index)
        else:
            band_gap = float(0.0 if gap_value is _MISSING else gap_value)
            e_hull = float(0.0 if hull_value is _MISSING else hull_value)
        metadata.update(
            {
                "wbm_index": _info_value(info, "WBM_idx", index),
                "step": _info_value(info, "WBM_step", None),
            }
        )
        records.append(
            {
                "material_id": material_id,
                "formula": composition.reduced_formula,
                "composition": composition,
                "reduced_composition": reduced,
                "nelems": len(reduced),
                "band_gap": band_gap,
                "e_hull": e_hull,
                "structure": structure,
                "primitive_structure": structure.get_primitive_structure(),
                "source": "wbm",
                "source_metadata": metadata,
            }
        )
        material_ids.add(material_id)
    df = pd.DataFrame.from_records(records).set_index("material_id")
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    df.to_pickle(output)
    return df
