"""Pair-screening core: grouping, environment matching, filters, pairing."""

from .envmatch import StructureGroup, find_unique_envs, group_similar_structures, swap_elem_by_X
from .filters import (
    apply_element_exclusion,
    apply_size_gate,
    has_gap_diversity,
    is_valence_assignable,
    valence_filter,
)
from .grouping import attach_band_gaps, group_by_composition_template
from .pairing import (
    attach_gaps_and_compress,
    enumerate_pairs,
    gaps_valid,
    pairs_to_dataframe,
)

__all__ = [
    "StructureGroup",
    "find_unique_envs",
    "group_similar_structures",
    "swap_elem_by_X",
    "apply_element_exclusion",
    "apply_size_gate",
    "has_gap_diversity",
    "is_valence_assignable",
    "valence_filter",
    "attach_band_gaps",
    "group_by_composition_template",
    "attach_gaps_and_compress",
    "enumerate_pairs",
    "gaps_valid",
    "pairs_to_dataframe",
]
