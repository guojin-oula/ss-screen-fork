"""Stage 13: reproducible *screening-level* photodetector suitability indicators.

Only band-edge cutoff and wavelength coverage are inferred from band gaps.  No
responsivity, dark current, NEP, detectivity or response time is fabricated;
those quantities require external device-level measurements or simulations.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Mapping

PHOTON_ENERGY_EV_UM = 1.239841984  # hc/e in eV um (standard physical constants)
DEFAULT_TARGET_UM = 2.0
BAND_PRESETS_UM = {
    "近红外（NIR）：1.0 μm": 1.0,
    "短波红外（SWIR）：2.0 μm": 2.0,
    "中波红外（MWIR）：4.0 μm": 4.0,
    "长波红外（LWIR）：10.0 μm": 10.0,
}
DEVICE_COLUMNS = (
    "responsivity_A_W",
    "dark_current_A",
    "nep_W_sqrtHz",
    "rise_time_ms",
    "area_cm2",
    "detectivity_jones",
)
OUTPUT_COLUMNS = (
    "candidate_id", "pair_index", "comp_a", "comp_b", "classification",
    "fraction_b", "gap_eV", "gap_origin", "cutoff_um", "target_um",
    "band_match", "energy_above_hull_eV_per_atom", "dynamical_status",
    "hull_signal", *DEVICE_COLUMNS, "device_data_source", "data_origin", "caution",
)


def _number(value: object) -> float | None:
    """Parse only finite numeric evidence (empty/NaN/Inf are not evidence)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def read_csv(path: Path) -> list[dict[str, str]]:
    """Return data rows from UTF-8/UTF-8-BOM CSV; no arbitrary code execution."""
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def _measurement_for(
    row: Mapping[str, object], measurements: Mapping[str, Mapping[str, object]]
) -> Mapping[str, object]:
    key = str(row.get("recommendation_id") or row.get("pair_index") or "").strip()
    return measurements.get(key, {}) if key else {}


def index_measurements(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    """Accept Stage 13 device.csv with recommendation_id (or pair_index) as key."""
    indexed = {}
    for row in rows:
        key = str(row.get("recommendation_id") or row.get("pair_index") or "").strip()
        if key:
            indexed[key] = row
    return indexed


def assess_candidate(
    row: Mapping[str, object],
    target_um: float,
    measurements: Mapping[str, object] | None = None,
    *,
    data_origin: str = "工程结果",
) -> dict[str, object]:
    """Compute only physically supportable, clearly labelled band-edge estimates.

    Gap priority: explicitly supplied alloy gap > linear interpolation of two
    endmember gaps with reported alloy fraction.  Interpolation omits bowing,
    strain and defects, and MUST NOT be confused with measured alloy gap.
    """
    target = _number(target_um)
    if target is None or target <= 0:
        raise ValueError("目标波长必须为正的有限数值（μm）")
    measurements = measurements or {}
    candidate_id = str(row.get("recommendation_id") or row.get("pair_index") or "未编号")
    fraction = _number(row.get("actual_fraction_b"))
    if fraction is None:
        fraction = _number(row.get("target_fraction_b"))
    if fraction is not None and not (0 <= fraction <= 1):
        fraction = None

    gap = None
    origin = "无有效带隙数据"
    for key in ("alloy_gap_eV", "gap_alloy_eV", "band_gap_eV"):
        value = _number(row.get(key))
        if value is not None and value > 0:
            gap, origin = value, f"输入合金带隙（{key}）"
            break
    if gap is None:
        gap_a, gap_b = _number(row.get("gap_a_eV")), _number(row.get("gap_b_eV"))
        if (
            gap_a is not None and gap_a >= 0 and gap_b is not None
            and gap_b >= 0 and fraction is not None
        ):
            estimate = (1 - fraction) * gap_a + fraction * gap_b
            if estimate > 0:
                gap, origin = estimate, "端元带隙线性插值（未计弯曲参数，非实测）"

    cutoff = PHOTON_ENERGY_EV_UM / gap if gap is not None else None
    band_match = (
        "待补充带隙" if cutoff is None else
        "带隙覆盖" if target <= cutoff else "带隙不覆盖"
    )
    result: dict[str, object] = {
        "candidate_id": candidate_id,
        "pair_index": row.get("pair_index", ""),
        "comp_a": row.get("comp_a", ""),
        "comp_b": row.get("comp_b", ""),
        "classification": row.get("classification", ""),
        "fraction_b": fraction,
        "gap_eV": gap,
        "gap_origin": origin,
        "cutoff_um": cutoff,
        "target_um": target,
        "band_match": band_match,
        "energy_above_hull_eV_per_atom": row.get("energy_above_hull_eV_per_atom", ""),
        "dynamical_status": row.get("dynamical_status", ""),
        "hull_signal": row.get("hull_signal", ""),
        "device_data_source": "未提供",
        "data_origin": data_origin,
        "caution": "仅为带隙与证据级预筛；不能证明器件实际响应率、暗电流、噪声或响应速度",
    }
    valid_measurement = False
    for column in DEVICE_COLUMNS:
        value = _number(measurements.get(column))
        if value is not None and value >= 0:
            result[column] = value
            valid_measurement = True
        else:
            result[column] = None
    # Specific detectivity D* = sqrt(A)/NEP when area in cm^2 and NEP in W/sqrt(Hz).
    if result["detectivity_jones"] is None:
        area, nep = result["area_cm2"], result["nep_W_sqrtHz"]
        if area is not None and area > 0 and nep is not None and nep > 0:
            result["detectivity_jones"] = math.sqrt(area) / nep
            valid_measurement = True
    if valid_measurement:
        result["device_data_source"] = (
            "内置虚构器件指标（仅演示）"
            if data_origin.startswith("内置演示")
            else "外部提供的器件数据"
        )
    return result


def assess_rows(
    rows: list[Mapping[str, object]], target_um: float,
    measurements: Mapping[str, Mapping[str, object]] | None = None,
    *, data_origin: str = "工程结果",
) -> list[dict[str, object]]:
    lookup = measurements or {}
    return [
        assess_candidate(
            row, target_um, _measurement_for(row, lookup), data_origin=data_origin
        )
        for row in rows
    ]


def export_rows(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


DEMO_ROWS: tuple[dict[str, str], ...] = (
    {
        "recommendation_id": "DEMO-001", "pair_index": "1", "comp_a": "演示端元A",
        "comp_b": "演示端元B", "classification": "uncertain", "gap_a_eV": "0.38",
        "gap_b_eV": "0.72", "target_fraction_b": "0.50",
        "dynamical_status": "not-evaluated", "hull_signal": "not-evaluated",
    },
    {
        "recommendation_id": "DEMO-002", "pair_index": "2", "comp_a": "演示端元C",
        "comp_b": "演示端元D", "classification": "uncertain", "gap_a_eV": "0.13",
        "gap_b_eV": "0.23", "target_fraction_b": "0.30",
        "dynamical_status": "not-evaluated", "hull_signal": "not-evaluated",
    },
    {
        "recommendation_id": "DEMO-003", "pair_index": "3", "comp_a": "演示端元E",
        "comp_b": "演示端元F", "classification": "uncertain", "gap_a_eV": "1.6",
        "gap_b_eV": "2.0", "target_fraction_b": "0.70",
        "dynamical_status": "not-evaluated", "hull_signal": "not-evaluated",
    },
)


# Fictitious instrument values exclusively for GUI demo mode. Not scientific evidence.
DEMO_DEVICE_ROWS: tuple[dict[str, str], ...] = (
    {
        "recommendation_id": "DEMO-001", "responsivity_A_W": "0.8",
        "dark_current_A": "1e-9", "nep_W_sqrtHz": "4e-12",
        "rise_time_ms": "0.9", "area_cm2": "0.01",
    },
    {
        "recommendation_id": "DEMO-002", "responsivity_A_W": "0.6",
        "dark_current_A": "8e-9", "nep_W_sqrtHz": "2e-11",
        "rise_time_ms": "2.4", "area_cm2": "0.02",
    },
    {
        "recommendation_id": "DEMO-003", "responsivity_A_W": "0.2",
        "dark_current_A": "2e-12", "nep_W_sqrtHz": "8e-13",
        "rise_time_ms": "0.25", "area_cm2": "0.01",
    },
)
