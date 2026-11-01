"""Tests for feeding external band-gap results back into pair generation."""

from __future__ import annotations

import pandas as pd
import pytest

from ssscreen.data.io import dump_group_df
from ssscreen.pair.envmatch import StructureGroup
from ssscreen.pair.gap_feedback import compare_gap_methods, generate_pairs_from_gap_results


def _groups() -> list[StructureGroup]:
    return [
        StructureGroup(
            entry_idx=[0, 1, 2],
            A_elements=[["Ca"], ["Ca"], ["Ca"]],
            compositions=["CaS", "CaSe", "CaTe"],
            group_size=3,
            X_element=["S", "Se", "Te"],
            mp_ids=["mp-low", "mp-mid", "mp-missing"],
            group_repr="descriptor",
            band_gaps=[0.0, 0.3, 0.5],
        )
    ]


def test_generate_pairs_from_gap_results_reports_coverage_and_writes_pairs(tmp_path):
    groups_path = tmp_path / "groups.json"
    gaps_path = tmp_path / "gap_results.csv"
    output = tmp_path / "pairs.csv"
    summary = tmp_path / "summary.json"
    dump_group_df(_groups(), groups_path)
    pd.DataFrame(
        [
            {
                "material_id": "mp-low",
                "formula": "CaS",
                "method": "hse06",
                "band_gap": 0.05,
                "is_direct": False,
                "transition": "indirect",
                "status": "success",
            },
            {
                "material_id": "mp-mid",
                "formula": "CaSe",
                "method": "hse06",
                "band_gap": 0.35,
                "is_direct": True,
                "transition": "G-G",
                "status": "success",
            },
            {
                "material_id": "mp-missing",
                "formula": "CaTe",
                "method": "hse06",
                "band_gap": 0.45,
                "is_direct": True,
                "transition": "G-G",
                "status": "failed",
            },
        ]
    ).to_csv(gaps_path, index=False)

    pairs, report = generate_pairs_from_gap_results(
        groups_path=groups_path,
        gap_paths=[gaps_path],
        output=output,
        summary=summary,
        method="hse06",
    )

    assert len(pairs) == 1
    row = pairs.iloc[0]
    assert row["mp_id_a"] == "mp-low"
    assert row["mp_id_b"] == "mp-mid"
    assert row["gap_method"] == "hse06"
    assert output.exists()
    assert summary.exists()
    assert report["materials_in_groups"] == 3
    assert report["successful_gap_rows"] == 2
    assert report["covered_materials"] == 2
    assert report["missing_materials"] == ["mp-missing"]
    assert report["groups_with_pairs"] == 1


def test_generate_pairs_from_gap_results_accepts_blank_failed_gap_rows(tmp_path):
    groups_path = tmp_path / "groups.json"
    gaps_path = tmp_path / "gap_results.csv"
    dump_group_df(_groups(), groups_path)
    pd.DataFrame(
        [
            {
                "material_id": "mp-low",
                "formula": "CaS",
                "method": "hse06",
                "band_gap": 0.05,
                "is_direct": False,
                "transition": "indirect",
                "status": "success",
            },
            {
                "material_id": "mp-mid",
                "formula": "CaSe",
                "method": "hse06",
                "band_gap": 0.35,
                "is_direct": True,
                "transition": "G-G",
                "status": "success",
            },
            {
                "material_id": "mp-missing",
                "formula": "CaTe",
                "method": "hse06",
                "band_gap": "",
                "is_direct": "",
                "transition": "",
                "status": "failed",
            },
        ]
    ).to_csv(gaps_path, index=False)

    pairs, report = generate_pairs_from_gap_results(
        groups_path=groups_path,
        gap_paths=[gaps_path],
        output=tmp_path / "pairs.csv",
        method="hse06",
    )

    assert len(pairs) == 1
    assert report["failed_or_skipped_gap_rows"] == 1
    assert report["missing_materials"] == ["mp-missing"]


def test_generate_pairs_from_gap_results_requires_method_for_ambiguous_sources(tmp_path):
    groups_path = tmp_path / "groups.json"
    gaps_path = tmp_path / "gap_results.csv"
    dump_group_df(_groups(), groups_path)
    pd.DataFrame(
        [
            {
                "material_id": "mp-low",
                "formula": "CaS",
                "method": "hse06",
                "band_gap": 0.05,
                "is_direct": False,
                "transition": "indirect",
                "status": "success",
            },
            {
                "material_id": "mp-low",
                "formula": "CaS",
                "method": "mbj",
                "band_gap": 0.02,
                "is_direct": False,
                "transition": "indirect",
                "status": "success",
            },
        ]
    ).to_csv(gaps_path, index=False)

    try:
        generate_pairs_from_gap_results(
            groups_path=groups_path,
            gap_paths=[gaps_path],
            output=tmp_path / "pairs.csv",
        )
    except ValueError as exc:
        assert "multiple gap methods" in str(exc)
    else:
        raise AssertionError("expected ambiguous gap methods to fail")


def test_generate_pairs_from_gap_results_rejects_duplicate_success_rows(tmp_path):
    groups_path = tmp_path / "groups.json"
    gaps_path = tmp_path / "gap_results.csv"
    dump_group_df(_groups(), groups_path)
    row = {
        "material_id": "mp-low",
        "formula": "CaS",
        "method": "hse06",
        "band_gap": 0.05,
        "is_direct": False,
        "transition": "indirect",
        "status": "success",
    }
    pd.DataFrame([row, row]).to_csv(gaps_path, index=False)

    with pytest.raises(ValueError, match="duplicate successful gap results"):
        generate_pairs_from_gap_results(
            groups_path=groups_path,
            gap_paths=[gaps_path],
            output=tmp_path / "pairs.csv",
            method="hse06",
        )


def test_compare_gap_methods_writes_method_outputs_and_summary(tmp_path):
    groups_path = tmp_path / "groups.json"
    gaps_path = tmp_path / "gap_results.csv"
    output_dir = tmp_path / "comparison"
    summary = tmp_path / "comparison.json"
    dump_group_df(_groups(), groups_path)
    pd.DataFrame(
        [
            {
                "material_id": "mp-low",
                "formula": "CaS",
                "method": "hse06",
                "band_gap": 0.05,
                "is_direct": False,
                "transition": "indirect",
                "status": "success",
            },
            {
                "material_id": "mp-mid",
                "formula": "CaSe",
                "method": "hse06",
                "band_gap": 0.35,
                "is_direct": True,
                "transition": "G-G",
                "status": "success",
            },
            {
                "material_id": "mp-low",
                "formula": "CaS",
                "method": "mbj",
                "band_gap": 0.05,
                "is_direct": False,
                "transition": "indirect",
                "status": "success",
            },
            {
                "material_id": "mp-mid",
                "formula": "CaSe",
                "method": "mbj",
                "band_gap": 0.9,
                "is_direct": True,
                "transition": "G-G",
                "status": "success",
            },
        ]
    ).to_csv(gaps_path, index=False)

    report = compare_gap_methods(
        groups_path=groups_path,
        gap_paths=[gaps_path],
        output_dir=output_dir,
        summary=summary,
    )

    assert report["methods"] == ["hse06", "mbj"]
    assert report["pair_counts"] == {"hse06": 1, "mbj": 0}
    assert report["common_pairs"] == []
    assert report["method_only_pairs"]["hse06"] == ["mp-low|mp-mid"]
    assert report["method_only_pairs"]["mbj"] == []
    assert report["gap_shifts"]["mp-low|mp-mid"]["mbj_minus_hse06"]["gap_b"] == 0.55
    assert report["directness_changes"]["mp-low|mp-mid"] == {
        "hse06": [False, True],
        "mbj": [False, True],
    }
    assert (output_dir / "pairs_hse06.csv").exists()
    assert (output_dir / "pairs_mbj.csv").exists()
    assert summary.exists()
