"""Regression checks for Stage 13 screening-only detector indicators."""

import csv
import math

import pytest

from ssscreen.detector import (
    DEMO_DEVICE_ROWS, DEMO_ROWS, PHOTON_ENERGY_EV_UM, assess_candidate, assess_rows,
    export_rows, index_measurements, read_csv,
)


def test_linear_endmember_estimate_and_cutoff():
    result = assess_candidate(
        {"recommendation_id": "test-1", "gap_a_eV": "0.4", "gap_b_eV": "0.8",
         "actual_fraction_b": "0.5"}, 2.0
    )
    assert result["gap_eV"] == pytest.approx(0.6)
    assert result["cutoff_um"] == pytest.approx(PHOTON_ENERGY_EV_UM / 0.6)
    assert result["band_match"] == "带隙覆盖"
    assert "线性插值" in result["gap_origin"]
    assert result["responsivity_A_W"] is None


def test_supplied_alloy_gap_takes_precedence():
    result = assess_candidate(
        {"pair_index": "2", "alloy_gap_eV": "0.2", "gap_a_eV": "0.5",
         "gap_b_eV": "0.9", "target_fraction_b": "0.5"}, 8.0
    )
    assert result["gap_eV"] == 0.2
    assert result["band_match"] == "带隙不覆盖"
    assert "输入合金带隙" in result["gap_origin"]


def test_no_gap_when_fraction_missing_or_nonfinite():
    for fraction in ("", "nan", "Infinity", "-0.2", "2.0"):
        result = assess_candidate(
            {"gap_a_eV": "0.2", "gap_b_eV": "0.5", "target_fraction_b": fraction},
            2.0,
        )
        assert result["gap_eV"] is None
        assert result["band_match"] == "待补充带隙"


def test_external_device_values_are_not_invented():
    measurements = index_measurements([{
        "recommendation_id": "test-a", "responsivity_A_W": "0.8", "area_cm2": "0.01",
        "nep_W_sqrtHz": "1e-12", "dark_current_A": "", "rise_time_ms": "0.4",
    }])
    assessed = assess_rows([{"recommendation_id": "test-a"}], 2.0, measurements)[0]
    assert assessed["responsivity_A_W"] == 0.8
    assert assessed["dark_current_A"] is None
    assert assessed["detectivity_jones"] == pytest.approx(1e11)
    assert assessed["device_data_source"] == "外部提供的器件数据"


def test_invalid_target_wavelength():
    for target in (0, -1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            assess_candidate({}, target)


def test_demo_flag_and_export(tmp_path):
    rows = assess_rows(
        list(DEMO_ROWS), 2.0, index_measurements([dict(r) for r in DEMO_DEVICE_ROWS]),
        data_origin="内置演示（非真实材料）",
    )
    assert len(rows) == 3
    assert all(row["data_origin"] == "内置演示（非真实材料）" for row in rows)
    output = tmp_path / "13_detector" / "assessed.csv"
    export_rows(output, rows)
    parsed = read_csv(output)
    assert len(parsed) == 3
    assert parsed[0]["candidate_id"] == "DEMO-001"
    assert parsed[0]["responsivity_A_W"] == "0.8"
    assert parsed[0]["device_data_source"] == "内置虚构器件指标（仅演示）"
