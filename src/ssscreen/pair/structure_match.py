"""Stage 3 structure matching from composition candidates and condensed archives."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..data.io import CondenseLoader
from .envmatch import StructureGroup, find_unique_envs, group_similar_structures
from .grouping import attach_band_gaps


def _candidate_entries(template_df: pd.DataFrame) -> list[list]:
    return [
        [str(row.material_id), str(row.x_element), float(row.band_gap)]
        for row in template_df.itertuples(index=False)
    ]


def match_structure_candidates(
    candidates: str | Path | pd.DataFrame,
    condensed_dirs: list[str | Path],
    *,
    min_x_elements: int = 2,
) -> tuple[list[StructureGroup], dict]:
    """Run envmatch on pre-screened composition candidates.

    Parameters
    ----------
    candidates
        Stage 1a composition-candidate CSV or an equivalent DataFrame. Required
        columns are ``template``, ``material_id``, ``x_element``, ``composition``
        or ``formula``, and ``band_gap``.
    condensed_dirs
        One or more Stage 2 archive directories containing ``{material_id}.json``.
    min_x_elements
        Minimum number of distinct X elements required for a structure group to
        survive. The default preserves the alloy-screening requirement.
    """
    df = pd.read_csv(candidates) if not isinstance(candidates, pd.DataFrame) else candidates.copy()
    loader = CondenseLoader(condensed_dirs)

    all_groups: list[StructureGroup] = []
    raw_group_count = 0
    missing_material_ids: list[str] = []
    invalid_material_ids: list[str] = []
    invalid_errors: dict[str, str] = {}

    for template, template_df in df.groupby("template", sort=False):
        entries = _candidate_entries(template_df)
        valid_entries = []
        material_ids = []
        condensed = []
        for entry in entries:
            material_id = entry[0]
            item = loader.get_condensed(material_id)
            if item is None:
                missing_material_ids.append(material_id)
                continue
            try:
                find_unique_envs([item])
            except Exception as exc:
                invalid_material_ids.append(material_id)
                invalid_errors[material_id] = str(exc)
                continue
            valid_entries.append(entry)
            material_ids.append(material_id)
            condensed.append(item)

        if len(condensed) < 2:
            continue
        try:
            envs = find_unique_envs(condensed)
            groups = group_similar_structures(envs, str(template), material_ids)
        except Exception as exc:
            invalid_material_ids.extend(material_ids)
            invalid_errors.update({material_id: str(exc) for material_id in material_ids})
            continue
        attach_band_gaps(groups, valid_entries)
        raw_group_count += len(groups)
        all_groups.extend(group for group in groups if len(set(group.X_element)) >= min_x_elements)

    report = {
        "candidate_rows": int(len(df)),
        "template_count": int(df["template"].nunique()) if len(df) else 0,
        "missing_descriptions": int(len(missing_material_ids)),
        "missing_material_ids": missing_material_ids,
        "invalid_descriptions": int(len(invalid_material_ids)),
        "invalid_material_ids": invalid_material_ids,
        "invalid_errors": invalid_errors,
        "raw_group_count": int(raw_group_count),
        "group_count": int(len(all_groups)),
        "grouped_members": int(sum(group.group_size for group in all_groups)),
        "min_x_elements": int(min_x_elements),
    }
    return all_groups, report
