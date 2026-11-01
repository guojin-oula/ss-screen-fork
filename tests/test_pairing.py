"""Tests for pair enumeration and the gaps_valid predicate."""

from __future__ import annotations

from ssscreen.config import PairThresholds
from ssscreen.pair.envmatch import StructureGroup
from ssscreen.pair.pairing import (
    enumerate_pairs,
    gaps_valid,
    pairs_to_dataframe,
)


def _group(comps, mp_ids, gaps=None):
    return StructureGroup(
        entry_idx=list(range(len(comps))),
        A_elements=[["Ca"]],
        compositions=comps,
        group_size=len(comps),
        X_element=["?"] * len(comps),
        mp_ids=mp_ids,
        group_repr="r",
        band_gaps=gaps or [],
    )


# ---------------------------------------------------------------------------
# gaps_valid
# ---------------------------------------------------------------------------
def test_gaps_valid_meets_rule():
    t = PairThresholds()
    # One low (<0.15) + one direct in (0.15, 1.5).
    gaps = [[0.0, True], [0.3, True]]
    assert gaps_valid(gaps, t)


def test_gaps_valid_missing_low_member():
    t = PairThresholds()
    gaps = [[0.3, True], [0.4, False]]  # no low member
    assert not gaps_valid(gaps, t)


def test_gaps_valid_missing_direct_member():
    t = PairThresholds()
    gaps = [[0.0, False], [0.05, False]]  # no direct in (0.15,1.5)
    assert not gaps_valid(gaps, t)


def test_gaps_valid_gap_too_large():
    t = PairThresholds()
    gaps = [[0.0, True], [2.0, True]]  # direct but beyond direct_max
    assert not gaps_valid(gaps, t)


# ---------------------------------------------------------------------------
# enumerate_pairs
# ---------------------------------------------------------------------------
def test_enumerate_pairs_keeps_complementary_gaps():
    t = PairThresholds()
    g = _group(["CaS", "CaSe"], ["mp-1", "mp-2"])
    gaps = [[0.0, True], [0.3, True]]
    pairs = enumerate_pairs(g, gaps, t)
    assert len(pairs) == 1
    p = pairs[0]
    assert p["comp_a"] == "CaS" and p["comp_b"] == "CaSe"
    assert p["gap_a"] == 0.0 and p["gap_b"] == 0.3
    assert p["gap_direct_a"] is True and p["gap_direct_b"] is True


def test_enumerate_pairs_skips_when_neither_below_threshold():
    t = PairThresholds()  # pair_any_below=0.3
    g = _group(["CaS", "CaSe"], ["mp-1", "mp-2"])
    gaps = [[0.5, True], [0.6, True]]  # both above 0.3
    assert enumerate_pairs(g, gaps, t) == []


def test_enumerate_pairs_skips_when_neither_above_threshold():
    t = PairThresholds()  # pair_any_above=0.2
    g = _group(["CaS", "CaSe"], ["mp-1", "mp-2"])
    gaps = [[0.0, True], [0.1, True]]  # both below 0.2
    assert enumerate_pairs(g, gaps, t) == []


def test_enumerate_pairs_skips_when_either_too_large():
    t = PairThresholds()  # pair_both_below=0.8
    g = _group(["CaS", "CaSe"], ["mp-1", "mp-2"])
    gaps = [[0.0, True], [1.0, True]]  # one exceeds 0.8
    assert enumerate_pairs(g, gaps, t) == []


def test_enumerate_pairs_skips_identical_compositions():
    t = PairThresholds()
    g = _group(["CaS", "CaS"], ["mp-1", "mp-2"])
    gaps = [[0.0, True], [0.3, True]]
    assert enumerate_pairs(g, gaps, t) == []


def test_pairs_to_dataframe_schema():
    t = PairThresholds()
    g = _group(["CaS", "CaSe"], ["mp-1", "mp-2"])
    pairs = enumerate_pairs(g, [[0.0, True], [0.3, True]], t)
    df = pairs_to_dataframe(pairs)
    assert list(df.columns) == [
        "comp_a",
        "comp_b",
        "gap_a",
        "gap_b",
        "mp_id_a",
        "mp_id_b",
        "gap_direct_a",
        "gap_direct_b",
    ]


def test_pairs_to_dataframe_empty():
    df = pairs_to_dataframe([])
    assert df.empty
