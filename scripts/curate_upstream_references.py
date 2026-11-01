#!/usr/bin/env python3
"""Curate read-only historical notebooks and source files into ``references/``."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Family:
    """Configuration for one upstream research-source family."""

    source_name: str
    destination: str
    roles: tuple[str, ...]


@dataclass(frozen=True)
class Candidate:
    """One notebook, source file, or source-document candidate."""

    path: Path
    source_path: str
    family: Family
    kind: str
    is_revision: bool


@dataclass(frozen=True)
class Excluded:
    """One reviewed file or directory that must remain external."""

    source_path: str
    reason: str


FAMILIES = (
    Family(
        "pair-screening",
        "pair-screening",
        ("data-loading", "structure-grouping", "pair-enumeration"),
    ),
    Family("mp-condense", "mp-condense", ("robocrys-condensation",)),
    Family("wbm-dataset", "wbm-dataset", ("wbm-preparation",)),
    Family("screen-mbj", "screen-mbj", ("band-workflows", "band-analysis")),
    Family("screen-promising", "screen-promising", ("band-verification",)),
    Family(
        "screen-antiperovskite",
        "screen-antiperovskite",
        ("prototype-generation", "stability", "band-workflows"),
    ),
    Family("rocksalt", "prototypes/rocksalt", ("prototype-study", "sqs")),
    Family("zincblend", "prototypes/zincblend", ("prototype-study",)),
    Family("Chalcopyrite ", "prototypes/chalcopyrite", ("prototype-study",)),
    Family("simple-defects", "simple-defects", ("vacancy-workflows", "defect-ranking")),
    Family("old-screen-202411", "old-screen-202411", ("historical-baseline",)),
)

FAMILY_KNOWLEDGE = {
    "pair-screening": {
        "title": "Pair screening",
        "purpose": "MP/WBM loading, valence filtering, structure grouping, gap feedback, and pair enumeration.",
        "coverage": "Core behavior is largely migrated to `src/ssscreen/data` and `src/ssscreen/pair`.",
        "defects": "Historical files include the `__getitem___` typo, stale ternary logic, and legacy schema spellings.",
    },
    "mp-condense": {
        "title": "Robocrys condensation",
        "purpose": "Single and batch robocrys condensation plus combined-archive construction.",
        "coverage": "A more robust implementation exists in `src/ssscreen/data/condense.py`.",
        "defects": "Historical workers swallow failures and contain fixed paths and worker counts.",
    },
    "wbm-dataset": {
        "title": "WBM preparation",
        "purpose": "WBM entry reconciliation, metadata validation, extxyz conversion, and condensation helpers.",
        "coverage": "Extxyz consumption is migrated; raw entry/summary reconciliation remains partial.",
        "defects": "The full WBM dataset remains external; historical scripts rely on fixed clean/dirty boundaries.",
    },
    "screen-mbj": {
        "title": "Band screening workflows",
        "purpose": "VASP and ABACUS PBE/HSE06/mBJ launch, recovery, k-path, analysis, and export flows.",
        "coverage": "The package provides external gap file contracts but not native DFT execution.",
        "defects": "Names, method labels, node IDs, resources, queues, and concurrency are historically site-specific.",
    },
    "screen-promising": {
        "title": "Promising-material band verification",
        "purpose": "PBE/HSE band workflows, MP structure acquisition, analysis, and result plots.",
        "coverage": "Not migrated beyond the package's external gap-result contract.",
        "defects": "`pbe-example.py` has syntax/name errors and a misleading HSE label.",
    },
    "screen-antiperovskite": {
        "title": "Antiperovskite screening",
        "purpose": "Prototype enumeration, MACE relaxation, mBJ/HSE launch, and hull analysis.",
        "coverage": "Generic SQS support exists; prototype relaxation and hull workflows remain unmigrated.",
        "defects": "Two historical notebooks required MP credential redaction; paths and calculator settings are site-specific.",
    },
    "prototypes/rocksalt": {
        "title": "Rocksalt prototype studies",
        "purpose": "Rocksalt builders, endmember HSE/mBJ/SOC studies, PbSe-Te SQS, and band plots.",
        "coverage": "Generic SQS structure generation covers only part of this workflow.",
        "defects": "Historical notebooks contain site-specific nodes/resources and one retained error output.",
    },
    "prototypes/zincblend": {
        "title": "Zincblende prototype studies",
        "purpose": "Zincblende builders and HSE/mBJ/SOC comparisons, including ABACUS launch knowledge.",
        "coverage": "No package-native DFT workflow is implemented.",
        "defects": "Submission settings are machine-specific and are historical examples only.",
    },
    "prototypes/chalcopyrite": {
        "title": "Chalcopyrite prototype studies",
        "purpose": "CdSnSb2 PBE/HSE/mBJ/SOC workflows and executed band-analysis plots.",
        "coverage": "No package-native DFT workflow is implemented.",
        "defects": "Historical AiiDA paths, resources, and node selections are not portable defaults.",
    },
    "simple-defects": {
        "title": "Vacancy and defect workflows",
        "purpose": "Elemental references, manual/workchain vacancies, chemical potentials, SQS vacancies, and ranking.",
        "coverage": "The planned `ssscreen.defects` layer is not implemented.",
        "defects": "Notebook variants contain fixed resources, nodes, supercells, and material-specific assumptions.",
    },
    "old-screen-202411": {
        "title": "Historical screening baseline",
        "purpose": "Older grouping/pairing logic and its threshold/direct-gap behavior.",
        "coverage": "Mostly superseded by the tested current screening core.",
        "defects": "Thresholds and directness policy differ from the current canonical workflow.",
    },
}

PRUNED_DIRECTORIES = {
    ".git",
    ".aiida",
    "__pycache__",
    "condensed",
    "structures",
    "hse_bandstructures",
    "pbe_bandstructures",
    "mbj_bandstructure",
    "mbj_bandstructure_sigma_0_005",
    "mace_relaxed",
}

PRUNED_REASONS = {
    ".git": "upstream Git metadata",
    ".aiida": "AiiDA process archive",
    "__pycache__": "Python bytecode cache",
    "condensed": "generated condensed-structure archive",
    "structures": "generated structure archive",
    "hse_bandstructures": "generated band-plot directory",
    "pbe_bandstructures": "generated band-plot directory",
    "mbj_bandstructure": "generated band-plot directory",
    "mbj_bandstructure_sigma_0_005": "generated band-plot directory",
    "mace_relaxed": "generated relaxed-structure directory",
}

SPECIFIC_EXCLUSIONS = {
    "wbm-dataset/summary.txt": "full dataset",
    "screen-mbj/struct-pks.txt": "external result/provenance sidecar",
    "zincblend/614426/_aiidasubmit.sh": "generated AiiDA scheduler artifact",
    "zincblend/614426/_scheduler-stdout.txt": "generated scheduler output",
    "zincblend/614426/_scheduler-stderr.txt": "generated scheduler output",
}

REDACTION_SOURCE_PATHS = {
    "screen-antiperovskite/mpset-test.ipynb",
    "screen-antiperovskite/satbility-mp.ipynb",
    "screen-antiperovskite/.ipynb_checkpoints/mpset-test-checkpoint.ipynb",
    "screen-antiperovskite/.ipynb_checkpoints/satbility-mp-checkpoint.ipynb",
}

CREDENTIAL_CALL_RE = re.compile(
    r"MPRester\(\s*(?P<quote>['\"])(?P<credential>[^'\"]{8,})(?P=quote)\s*\)"
)
NAMED_SECRET_RE = re.compile(
    r"(?i)(?:api[_-]?key|token|password|secret)\s*[:=]\s*['\"][^'\"]{8,}['\"]"
)

KNOWN_DEFECTS_BY_PATH = {
    "pair-screening/envmatch.py": ["StructureGroup.__getitem___ is misspelled"],
    "pair-screening/screening-tenary.ipynb": ["stale inlined envmatch implementation"],
    "screen-promising/pbe-example.py": [
        "syntax error in import",
        "calls an undefined HSE helper and uses a misleading HSE label",
    ],
}

PORTABILITY_NOTES = {
    "screen-mbj": ["contains site-specific AiiDA nodes, groups, codes, queues, and resources"],
    "screen-promising": [
        "contains site-specific AiiDA nodes, groups, codes, queues, and resources"
    ],
    "screen-antiperovskite": [
        "contains site-specific AiiDA settings and historical calculator/model paths"
    ],
    "prototypes/rocksalt": ["contains site-specific AiiDA nodes, groups, codes, and resources"],
    "prototypes/zincblend": ["contains site-specific scheduler and calculator configuration"],
    "prototypes/chalcopyrite": ["contains site-specific AiiDA nodes, groups, codes, and resources"],
    "simple-defects": ["contains material-specific assumptions and site-specific AiiDA settings"],
}

EXTERNAL_DEPENDENCIES = {
    "pair-screening": ["Materials Project/WBM tables", "robocrys condensed JSON archives"],
    "mp-condense": ["Materials Project structures", "robocrys"],
    "wbm-dataset": ["WBM step_1..step_5 archives", "WBM summary table"],
    "screen-mbj": ["AiiDA profile and calculation nodes", "VASP/ABACUS codes"],
    "screen-promising": ["AiiDA profile and calculation nodes", "Materials Project structures"],
    "screen-antiperovskite": ["AiiDA profile", "MACE model", "Materials Project entries"],
    "prototypes/rocksalt": ["AiiDA profile and calculation nodes", "VASP code"],
    "prototypes/zincblend": ["AiiDA profile and calculation nodes", "VASP/ABACUS codes"],
    "prototypes/chalcopyrite": ["AiiDA profile and calculation nodes", "VASP code"],
    "simple-defects": ["AiiDA profile and calculation nodes", "VASP code", "doped/matchest"],
    "old-screen-202411": ["Materials Project/WBM tables", "robocrys condensed JSON archives"],
}


class CurationError(RuntimeError):
    """Raised when historical content violates the approved curation policy."""


def _kind_for(relative: Path) -> str | None:
    if relative.suffix == ".ipynb":
        return "notebook"
    if relative.suffix == ".py":
        return "python-source"
    if relative.as_posix() == "README.txt":
        return "source-documentation"
    if relative.as_posix() == "614426-abacus/submit.sh":
        return "shell-source"
    return None


def _unselected_reason(relative: Path) -> str:
    name = relative.name.lower()
    suffixes = {suffix.lower() for suffix in relative.suffixes}
    if suffixes & {".bz2", ".gz", ".tgz", ".zip", ".tar"}:
        return "dataset or archive outside notebook/source scope"
    if suffixes & {".csv", ".json", ".df", ".xyz", ".xml", ".log"}:
        return "data or calculated-result artifact"
    if suffixes & {".cif", ".res", ".cell", ".orb", ".upf"}:
        return "structure or calculator-input artifact"
    if name in {"incar", "kpoints", "poscar", "potcar", "input", "stru"}:
        return "calculator-input artifact"
    if name.startswith("."):
        return "repository metadata outside curation scope"
    return "non-source artifact outside approved curation scope"


def discover_candidates(workspace_root: Path) -> tuple[list[Candidate], list[Excluded]]:
    """Return approved source candidates and reviewed exclusions."""

    workspace_root = Path(workspace_root)
    candidates: list[Candidate] = []
    exclusions: list[Excluded] = []

    for family in FAMILIES:
        root = workspace_root / family.source_name
        if not root.is_dir():
            continue
        for base, directories, filenames in os.walk(root):
            base_path = Path(base)
            kept_directories: list[str] = []
            for directory in sorted(directories):
                path = base_path / directory
                relative = path.relative_to(root)
                if directory in PRUNED_DIRECTORIES:
                    exclusions.append(
                        Excluded(
                            f"{family.source_name}/{relative.as_posix()}/",
                            PRUNED_REASONS[directory],
                        )
                    )
                else:
                    kept_directories.append(directory)
            directories[:] = kept_directories
            for filename in sorted(filenames):
                path = base_path / filename
                relative = path.relative_to(root)
                source_path = f"{family.source_name}/{relative.as_posix()}"
                if source_path in SPECIFIC_EXCLUSIONS:
                    exclusions.append(Excluded(source_path, SPECIFIC_EXCLUSIONS[source_path]))
                    continue
                kind = _kind_for(relative)
                if kind is None:
                    exclusions.append(Excluded(source_path, _unselected_reason(relative)))
                    continue
                candidates.append(
                    Candidate(
                        path=path,
                        source_path=source_path,
                        family=family,
                        kind=kind,
                        is_revision=".ipynb_checkpoints" in relative.parts,
                    )
                )

    return sorted(candidates, key=lambda item: item.source_path), sorted(
        exclusions, key=lambda item: item.source_path
    )


def destination_for(candidate: Candidate) -> Path:
    """Return the repository-relative path for a stored candidate."""

    relative = Path(candidate.source_path).relative_to(candidate.family.source_name)
    root = Path("references") / candidate.family.destination
    if candidate.is_revision:
        parts = [part for part in relative.parts if part != ".ipynb_checkpoints"]
        return root / "revisions" / Path(*parts)
    if candidate.kind == "notebook":
        return root / "notebooks" / relative
    return root / "source" / relative


def _source_text(cell: dict) -> str:
    source = cell.get("source", [])
    return source if isinstance(source, str) else "".join(source)


def _set_source_text(cell: dict, text: str) -> None:
    if isinstance(cell.get("source", []), str):
        cell["source"] = text
    else:
        cell["source"] = text.splitlines(keepends=True)


def redact_notebook(candidate: Candidate, raw: bytes) -> tuple[bytes, list[str]]:
    """Redact a reviewed credential while preserving all notebook results."""

    notebook = json.loads(raw)
    original = copy.deepcopy(notebook)
    matches: list[tuple[dict, re.Match[str]]] = []
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        matches.extend((cell, match) for match in CREDENTIAL_CALL_RE.finditer(_source_text(cell)))

    if not matches:
        return raw, []
    if candidate.source_path not in REDACTION_SOURCE_PATHS:
        raise CurationError(f"unexpected credential-like call in {candidate.source_path}")
    if len(matches) != 1:
        raise CurationError(
            f"expected one credential-like call in {candidate.source_path}, found {len(matches)}"
        )

    cell, _match = matches[0]
    _set_source_text(cell, CREDENTIAL_CALL_RE.sub("MPRester()", _source_text(cell), count=1))

    for before, after in zip(original.get("cells", []), notebook.get("cells", []), strict=True):
        before_without_source = {key: value for key, value in before.items() if key != "source"}
        after_without_source = {key: value for key, value in after.items() if key != "source"}
        if before_without_source != after_without_source:
            raise CurationError(f"redaction changed notebook results in {candidate.source_path}")

    curated = (json.dumps(notebook, ensure_ascii=False, indent=1) + "\n").encode()
    return curated, ["credential-redaction"]


def sha256_bytes(raw: bytes) -> str:
    """Return the lowercase SHA-256 hex digest for bytes."""

    return hashlib.sha256(raw).hexdigest()


def sha256_path(path: Path) -> str:
    """Return the lowercase SHA-256 hex digest for a file."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_record(
    candidate: Candidate,
    *,
    status: str,
    source_sha256: str,
    curated_path: str | None = None,
    curated_raw: bytes | None = None,
    alias_of: str | None = None,
    transformations: list[str] | None = None,
    snapshot_date: str,
    git_head: str | None,
    git_dirty: bool | None,
) -> dict[str, object]:
    record: dict[str, object] = {
        "source_path": candidate.source_path,
        "artifact_kind": candidate.kind,
        "family": candidate.family.destination,
        "scientific_roles": list(candidate.family.roles),
        "status": status,
        "source_sha256": source_sha256,
        "source_size_bytes": candidate.path.stat().st_size,
        "outputs_preserved": candidate.kind == "notebook",
        "transformations": transformations or [],
        "snapshot_date": snapshot_date,
        "source_git_head": git_head,
        "source_git_dirty": git_dirty,
        "known_defects": KNOWN_DEFECTS_BY_PATH.get(candidate.source_path, []),
        "portability_notes": PORTABILITY_NOTES.get(candidate.family.destination, []),
        "external_dependencies": EXTERNAL_DEPENDENCIES.get(candidate.family.destination, []),
        "license_status": "user-authorized-unspecified",
        "redistribution_basis": "user-confirmed-2026-07-21",
    }
    if curated_path is not None:
        record["curated_path"] = curated_path
    if curated_raw is not None:
        record["curated_sha256"] = sha256_bytes(curated_raw)
        record["curated_size_bytes"] = len(curated_raw)
    if alias_of is not None:
        record["alias_of"] = alias_of
    return record


def _git_provenance(root: Path) -> tuple[str | None, bool | None]:
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0 or Path(completed.stdout.strip()).resolve() != root.resolve():
        return None, None
    head = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return head, bool(status.strip())


def _write_indexes(repo_root: Path, manifest: dict[str, object]) -> None:
    references_root = repo_root / "references"
    counts = manifest["counts"]
    lines = [
        "# Historical upstream references",
        "",
        "These files preserve read-only research provenance. They are not canonical package code and must not be executed as a workflow without review.",
        "",
        f"Snapshot: `{manifest['snapshot_date']}`. Stored: {counts['stored']}; redacted: {counts['redacted']}; aliases: {counts['alias']}; excluded: {counts['excluded']}.",
        "",
        "Large datasets, calculation directories, archives, `.aiida` data, generated scheduler artifacts, and secrets remain external.",
        "",
        "## Source families",
        "",
    ]
    present_families = sorted(
        {
            str(record["family"])
            for record in manifest["artifacts"]
            if "family" in record and record["status"] != "excluded"
        }
    )
    for family in present_families:
        info = FAMILY_KNOWLEDGE[family]
        lines.append(f"- [{info['title']}]({family}/README.md) — {info['purpose']}")
    lines.extend(
        [
            "",
            "See [`manifest.json`](manifest.json) for original paths, hashes, aliases, transformations, exclusions, and provenance.",
            "",
        ]
    )
    (references_root / "README.md").write_text("\n".join(lines))

    records = manifest["artifacts"]
    for family in present_families:
        info = FAMILY_KNOWLEDGE[family]
        family_records = [record for record in records if record.get("family") == family]
        family_lines = [
            f"# {info['title']}",
            "",
            info["purpose"],
            "",
            f"**Current package coverage:** {info['coverage']}",
            "",
            f"**Historical cautions:** {info['defects']}",
            "",
            "Notebook outputs and execution state are preserved. External datasets and calculation artifacts referenced by these files are not included.",
            "",
            "## Artifacts",
            "",
        ]
        for record in sorted(family_records, key=lambda item: str(item["source_path"])):
            if "curated_path" in record:
                target = Path(str(record["curated_path"])).relative_to(Path("references") / family)
                family_lines.append(
                    f"- [`{record['source_path']}`]({target.as_posix()}) — {record['status']}"
                )
            else:
                family_lines.append(
                    f"- `{record['source_path']}` — alias of `{record['alias_of']}`"
                )
        family_lines.append("")
        readme = references_root / family / "README.md"
        readme.parent.mkdir(parents=True, exist_ok=True)
        readme.write_text("\n".join(family_lines))


def validate_archive(references_root: Path, manifest: dict[str, object]) -> None:
    """Raise if hashes, aliases, notebooks, exclusions, or secrets violate policy."""

    references_root = Path(references_root)
    repo_root = references_root.parent
    records = list(manifest.get("artifacts", []))
    by_source = {str(record["source_path"]): record for record in records}
    expected_files: set[Path] = set()

    for record in records:
        status = record["status"]
        if status == "excluded":
            if "curated_path" in record:
                raise CurationError(f"excluded artifact has curated path: {record['source_path']}")
            continue
        if status == "alias":
            target = by_source.get(str(record.get("alias_of")))
            if target is None or target.get("status") not in {"stored", "redacted"}:
                raise CurationError(f"invalid alias target for {record['source_path']}")
            if record["source_sha256"] != target["source_sha256"]:
                raise CurationError(f"alias hash mismatch for {record['source_path']}")
            continue

        curated_relative = Path(str(record["curated_path"]))
        if curated_relative.is_absolute() or ".." in curated_relative.parts:
            raise CurationError(f"unsafe curated path for {record['source_path']}")
        path = repo_root / curated_relative
        expected_files.add(path.resolve())
        if not path.is_file():
            raise CurationError(f"missing curated file for {record['source_path']}")
        actual_hash = sha256_path(path)
        if actual_hash != record["curated_sha256"]:
            raise CurationError(f"curated hash mismatch for {record['source_path']}")
        raw = path.read_bytes()
        if CREDENTIAL_CALL_RE.search(raw.decode(errors="replace")) or NAMED_SECRET_RE.search(
            raw.decode(errors="replace")
        ):
            raise CurationError(f"credential-like content remains in {record['source_path']}")
        if record["artifact_kind"] == "notebook":
            try:
                json.loads(raw)
            except json.JSONDecodeError as exc:
                raise CurationError(f"invalid notebook JSON for {record['source_path']}") from exc

    for path in references_root.rglob("*"):
        if not path.is_file():
            continue
        if path.name in {"README.md", "manifest.json"}:
            continue
        if path.resolve() not in expected_files:
            raise CurationError(f"unmanifested file in reference archive: {path}")


def curate(
    workspace_root: Path,
    repo_root: Path,
    snapshot_date: str,
    *,
    write: bool,
) -> dict[str, object]:
    """Curate approved historical sources and return the manifest."""

    workspace_root = Path(workspace_root)
    repo_root = Path(repo_root)
    candidates, exclusions = discover_candidates(workspace_root)
    records: list[dict[str, object]] = []
    canonical_by_hash: dict[str, str] = {}
    provenance = {
        family.source_name: _git_provenance(workspace_root / family.source_name)
        for family in FAMILIES
        if (workspace_root / family.source_name).is_dir()
    }

    for candidate in sorted(candidates, key=lambda item: (item.is_revision, item.source_path)):
        raw = candidate.path.read_bytes()
        source_sha256 = sha256_bytes(raw)
        alias_of = canonical_by_hash.get(source_sha256)
        if alias_of is not None:
            git_head, git_dirty = provenance[candidate.family.source_name]
            records.append(
                _artifact_record(
                    candidate,
                    status="alias",
                    source_sha256=source_sha256,
                    alias_of=alias_of,
                    snapshot_date=snapshot_date,
                    git_head=git_head,
                    git_dirty=git_dirty,
                )
            )
            continue

        canonical_by_hash[source_sha256] = candidate.source_path
        curated_raw, transformations = (
            redact_notebook(candidate, raw) if candidate.kind == "notebook" else (raw, [])
        )
        destination = destination_for(candidate)
        if write:
            output = repo_root / destination
            output.parent.mkdir(parents=True, exist_ok=True)
            if transformations:
                output.write_bytes(curated_raw)
            else:
                shutil.copyfile(candidate.path, output)
        records.append(
            _artifact_record(
                candidate,
                status="redacted" if transformations else "stored",
                source_sha256=source_sha256,
                curated_path=destination.as_posix(),
                curated_raw=curated_raw,
                transformations=transformations,
                snapshot_date=snapshot_date,
                git_head=provenance[candidate.family.source_name][0],
                git_dirty=provenance[candidate.family.source_name][1],
            )
        )

    records.extend(
        {
            "source_path": item.source_path,
            "artifact_kind": "excluded-artifact",
            "status": "excluded",
            "reason": item.reason,
            "snapshot_date": snapshot_date,
            "license_status": "not-copied",
            "redistribution_basis": "excluded-by-policy",
        }
        for item in exclusions
    )
    counts = Counter(str(record["status"]) for record in records)
    manifest: dict[str, object] = {
        "schema_version": 1,
        "snapshot_date": snapshot_date,
        "redistribution_basis": "user-confirmed-2026-07-21",
        "policy": {
            "canonical_implementation": "src/ssscreen",
            "notebook_outputs": "preserved",
            "byte_identical_duplicates": "manifest-alias",
            "large_data": "external",
            "secrets": "redacted",
        },
        "source_roots": [
            {
                "source_name": family.source_name,
                "destination": family.destination,
                "git_head": provenance.get(family.source_name, (None, None))[0],
                "git_dirty": provenance.get(family.source_name, (None, None))[1],
            }
            for family in FAMILIES
            if (workspace_root / family.source_name).is_dir()
        ],
        "counts": {
            status: counts.get(status, 0) for status in ("alias", "excluded", "redacted", "stored")
        },
        "artifacts": sorted(records, key=lambda item: str(item["source_path"])),
    }
    if write:
        root = repo_root / "references"
        root.mkdir(parents=True, exist_ok=True)
        (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        _write_indexes(repo_root, manifest)
    return manifest


def _summary(manifest: dict[str, object]) -> dict[str, object]:
    stored = [
        record for record in manifest["artifacts"] if record["status"] in {"stored", "redacted"}
    ]
    return {
        "counts": manifest["counts"],
        "curated_size_bytes": sum(int(record["curated_size_bytes"]) for record in stored),
        "largest_artifacts": [
            {
                "source_path": record["source_path"],
                "curated_size_bytes": record["curated_size_bytes"],
            }
            for record in sorted(
                stored, key=lambda item: int(item["curated_size_bytes"]), reverse=True
            )[:5]
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run curation, dry-run inventory, or independent archive validation."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", type=Path)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--snapshot-date")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)

    if args.validate_only:
        manifest_path = args.repo_root / "references" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        validate_archive(args.repo_root / "references", manifest)
        print(json.dumps({"status": "valid", **_summary(manifest)}, indent=2))
        return 0
    if args.workspace_root is None or args.snapshot_date is None:
        parser.error("--workspace-root and --snapshot-date are required for curation")

    manifest = curate(
        args.workspace_root,
        args.repo_root,
        args.snapshot_date,
        write=not args.dry_run,
    )
    if not args.dry_run:
        validate_archive(args.repo_root / "references", manifest)
    print(json.dumps(_summary(manifest), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
