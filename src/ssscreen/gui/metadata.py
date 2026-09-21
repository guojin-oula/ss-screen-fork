"""GUI-only presentation metadata for the existing ``ss-screen`` CLI.

Scientific defaults and validation continue to come from Click.  This module
only supplies display order, Chinese stage names, and convenient project-local
path presets for blank path options.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CommandPresentation:
    """Human-facing placement and title for a CLI command."""

    stage: str
    title: str
    command_path: tuple[str, ...]


STAGES: tuple[tuple[str, str, str], ...] = (
    ("00", "工作台", ""),
    ("01", "数据源", "01_dataset"),
    ("02", "组成模板筛选", "02_composition"),
    ("03", "结构描述归档", "03_condensed"),
    ("04", "结构匹配与材料分组", "04_groups"),
    ("05", "带隙交接", "05_gap"),
    ("06", "端元配对", "06_pair"),
    ("07", "SQS 合金", "07_sqs"),
    ("08", "MACE 驰豫", "08_relax"),
    ("09", "混合焓", "09_mixing"),
    ("10", "声子谱", "10_phonon"),
    ("11", "竞争相 / 凸包", "11_phase"),
    ("12", "综合推荐", "12_recommend"),
)


COMMANDS: tuple[CommandPresentation, ...] = (
    CommandPresentation("01", "Materials Project 数据获取", ("dataset", "mp")),
    CommandPresentation("01", "WBM 数据获取", ("dataset", "wbm")),
    CommandPresentation("01", "本地 POSCAR 结构导入", ("dataset", "structures")),
    CommandPresentation("02", "价态过滤", ("valence-filter",)),
    CommandPresentation("02", "组成模板筛选", ("composition-screen",)),
    CommandPresentation("03", "生成结构描述", ("condense",)),
    CommandPresentation("03", "建立归档索引", ("condense-index",)),
    CommandPresentation("03", "校验结构描述归档", ("condense-validate",)),
    CommandPresentation("04", "执行结构匹配", ("structure-match",)),
    CommandPresentation("04", "兼容一步式分组", ("group",)),
    CommandPresentation("05", "导出高精度带隙任务", ("gap-export",)),
    CommandPresentation("05", "收集 VASP 带隙结果", ("gap-collect-vasp",)),
    CommandPresentation("05", "校验外部带隙结果", ("gap-validate",)),
    CommandPresentation("06", "生成端元对", ("pair",)),
    CommandPresentation("06", "比较带隙方法", ("gap-compare",)),
    CommandPresentation("07", "生成 SQS", ("stability", "sqs-generate")),
    CommandPresentation("08", "MACE 结构驰豫", ("stability", "relax")),
    CommandPresentation("09", "混合焓计算", ("stability", "mixing-enthalpy")),
    CommandPresentation("10", "声子谱一步式运行", ("stability", "phonon-run")),
    CommandPresentation("11", "竞争相与凸包一步式运行", ("stability", "phase-diagram")),
    CommandPresentation("12", "综合推荐", ("recommend",)),
)


# Project-local conveniences only.  They fill otherwise-empty widgets; Click's
# own defaults remain authoritative for scientific/numerical parameters.
PATH_PRESETS: dict[tuple[str, ...], dict[str, Any]] = {
    ("dataset", "mp"): {
        "--output": "01_dataset/mp.df",
        "--provenance": "01_dataset/mp.df.provenance.json",
    },
    ("dataset", "wbm"): {"--output": "01_dataset/wbm.df"},
    ("dataset", "structures"): {
        "--input-dir": ("data/CaS_CaSe_CaTe_PBE_relaxed_CONTCAR",),
        "--output": "01_dataset/local_structures.df",
        "--provenance": "01_dataset/local_structures.provenance.json",
    },
    ("valence-filter",): {
        "--df-mp": "01_dataset/mp.df",
        "--output": "02_composition/valid_ids.json",
    },
    ("composition-screen",): {
        "--df": ("01_dataset/mp.df",),
        "--output": "02_composition/composition_candidates.csv",
        "--summary": "02_composition/composition_summary.json",
    },
    ("condense",): {
        "--df": "01_dataset/local_structures.df",
        "--output-dir": "03_condensed/local",
        "--manifest": "03_condensed/local_manifest.jsonl",
        "--index": "03_condensed/local_index.csv",
    },
    ("condense-index",): {
        "--condensed-dir": "03_condensed/local",
        "--output": "03_condensed/local_index.csv",
    },
    ("condense-validate",): {
        "--condensed-dir": "03_condensed/local",
        "--output": "03_condensed/local_validation.csv",
    },
    ("structure-match",): {
        "--candidates": "02_composition/composition_candidates.csv",
        "--condensed-dir": ("03_condensed/local",),
        "--output": "04_groups/groups.json",
        "--summary": "04_groups/structure_match_summary.json",
    },
    ("group",): {
        "--df-mp": "01_dataset/local_structures.df",
        "--condensed-dirs": ("03_condensed/local",),
        "--output": "04_groups/groups_legacy.json",
    },
    ("gap-export",): {
        "--groups": "04_groups/groups.json",
        "--dataset": "01_dataset/local_structures.df",
        "--method": "pbe-vasp-final-v1",
        "--structure-dir": "05_gap/structures",
        "--results-template": "05_gap/results_template.csv",
        "--method-metadata-template": "05_gap/method_metadata.json",
        "--output": "05_gap/tasks.csv",
    },
    ("gap-collect-vasp",): {
        "--tasks": "05_gap/tasks.csv",
        "--results-dir": "work/real-pbe-mace-20260914-run4/05_gap/vasp_by_task_id",
        "--method-metadata": "05_gap/method_metadata.json",
        "--output": "05_gap/results_returned.csv",
        "--report": "05_gap/collection-report.json",
    },
    ("gap-validate",): {
        "--gaps": "05_gap/results_returned.csv",
        "--tasks": "05_gap/tasks.csv",
        "--method-metadata": "05_gap/method_metadata.json",
        "--output": "05_gap/results_normalized.csv",
        "--rejected": "05_gap/results_rejected.csv",
        "--report": "05_gap/validation.json",
    },
    ("pair",): {
        "--groups": "04_groups/groups.json",
        "--gap-results": ("05_gap/results_normalized.csv",),
        "--summary": "06_pair/pair_summary.json",
        "--output": "06_pair/final_pairs.csv",
    },
    ("gap-compare",): {
        "--groups": "04_groups/groups.json",
        "--gap-results": ("05_gap/results_normalized.csv",),
        "--output-dir": "06_pair/gap_compare",
        "--summary": "06_pair/gap_compare_summary.json",
    },
    ("stability", "sqs-generate"): {
        "--pairs": "06_pair/final_pairs.csv",
        "--dataset": "01_dataset/local_structures.df",
        "--output-dir": "07_sqs/structures",
        "--manifest": "07_sqs/sqs_manifest.jsonl",
        "--supercell": "2,1,1",
        "--seed": "7",
    },
    ("stability", "relax"): {
        "--manifest": "07_sqs/sqs_manifest.jsonl",
        "--include-endmembers": True,
        "--model-path": "data/mace-mpa-0-medium.model",
        "--model-name": "mace-mpa-0-medium",
        "--device": "cuda:0",
        "--dtype": "float32",
        "--max-steps": "200",
        "--output-dir": "08_relax",
        "--results": "08_relax/relaxation_results.jsonl",
    },
    ("stability", "mixing-enthalpy"): {
        "--pairs": "06_pair/final_pairs.csv",
        "--relax-results": "08_relax/relaxation_results.jsonl",
        "--output": "09_mixing/mixing_enthalpy.csv",
        "--summary": "09_mixing/mixing_summary.json",
    },
    ("stability", "phonon-export"): {
        "--relax-results": "08_relax/relaxation_results.jsonl",
        "--output-dir": "10_phonon/tasks",
        "--manifest": "10_phonon/manifest.jsonl",
    },
    ("stability", "phonon-forces"): {
        "--manifest": "10_phonon/manifest.jsonl",
        "--model-path": "data/mace-mpa-0-medium.model",
        "--model-name": "mace-mpa-0-medium",
        "--device": "cuda:0",
        "--dtype": "float32",
        "--output-dir": "10_phonon/forces",
        "--results": "10_phonon/force_results.jsonl",
    },
    ("stability", "phonon-collect"): {
        "--manifest": "10_phonon/manifest.jsonl",
        "--force-results": "10_phonon/force_results.jsonl",
        "--output-dir": "10_phonon",
        "--summary": "10_phonon/phonon_summary.csv",
        "--report": "10_phonon/phonon_report.json",
    },
    ("stability", "phonon-run"): {
        "--relax-results": "08_relax/relaxation_results.jsonl",
        "--include-endmembers": True,
        "--supercell": "1,1,1",
        "--allow-loose-input": True,
        "--mesh": "6,6,6",
        "--band-points": "21",
        "--model-path": "data/mace-mpa-0-medium.model",
        "--model-name": "mace-mpa-0-medium",
        "--device": "cuda:0",
        "--dtype": "float32",
        "--output-dir": "10_phonon",
    },
    ("stability", "competing-export"): {
        "--relax-results": "08_relax/relaxation_results.jsonl",
        "--mp-backend": "api",
        "--thermo-type": "GGA_GGA+U",
        "--api-timeout": "180",
        "--output-dir": "11_phase/competing",
        "--manifest": "11_phase/competing_manifest.jsonl",
        "--report": "11_phase/competing_export_report.json",
    },
    ("stability", "competing-relax"): {
        "--manifest": "11_phase/competing_manifest.jsonl",
        "--model-path": "data/mace-mpa-0-medium.model",
        "--model-name": "mace-mpa-0-medium",
        "--device": "cuda:0",
        "--dtype": "float32",
        "--max-steps": "200",
        "--output-dir": "11_phase/competing_relaxed",
        "--results": "11_phase/competing_relaxation_results.jsonl",
    },
    ("stability", "convex-hull"): {
        "--relax-results": "08_relax/relaxation_results.jsonl",
        "--competing-manifest": "11_phase/competing_manifest.jsonl",
        "--competing-results": "11_phase/competing_relaxation_results.jsonl",
        "--output": "11_phase/phase_stability.csv",
        "--entries-output": "11_phase/hull_entries.csv",
        "--summary": "11_phase/summary.json",
    },
    ("stability", "phase-diagram"): {
        "--relax-results": "08_relax/relaxation_results.jsonl",
        "--mp-backend": "api",
        "--thermo-type": "GGA_GGA+U",
        "--api-timeout": "180",
        "--model-path": "data/mace-mpa-0-medium.model",
        "--model-name": "mace-mpa-0-medium",
        "--device": "cuda:0",
        "--dtype": "float32",
        "--max-steps": "200",
        "--allow-incomplete": True,
        "--output-dir": "11_phase",
    },
    ("recommend",): {
        "--pairs": "06_pair/final_pairs.csv",
        "--gap-results": "05_gap/results_normalized.csv",
        "--mixing-enthalpy": "09_mixing/mixing_enthalpy.csv",
        "--phonons": "10_phonon/phonon_summary.csv",
        "--phase-stability": "11_phase/phase_stability.csv",
        "--output": "12_recommend/recommendations.csv",
        "--report": "12_recommend/recommendation_report.md",
        "--summary": "12_recommend/recommendation_summary.json",
    },
}


def stage_title(stage_id: str) -> str:
    """Return a stable display name for a stage identifier."""
    for sid, name, _directory in STAGES:
        if sid == stage_id:
            return name
    return stage_id


def stage_directory(stage_id: str) -> str:
    """Return the conventional project directory for a stage."""
    for sid, _name, directory in STAGES:
        if sid == stage_id:
            return directory
    return ""
