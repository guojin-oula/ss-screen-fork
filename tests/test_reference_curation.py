"""Tests for deterministic curation of historical upstream references."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "curate_upstream_references.py"


def _load_module():
    assert SCRIPT.exists(), "curation script has not been implemented"
    spec = importlib.util.spec_from_file_location("curate_upstream_references", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _notebook(source: str, *, outputs: list[dict] | None = None) -> bytes:
    return json.dumps(
        {
            "cells": [
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "metadata": {},
                    "outputs": outputs or [],
                    "source": [source],
                }
            ],
            "metadata": {"kernelspec": {"name": "python3"}},
            "nbformat": 4,
            "nbformat_minor": 5,
        }
    ).encode()


def _write(path: Path, content: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content)


def test_discovery_classifies_primary_checkpoint_and_excluded_paths(tmp_path):
    module = _load_module()
    workspace = tmp_path / "HC"
    _write(workspace / "pair-screening" / "screening.ipynb", _notebook("x = 1\n"))
    _write(
        workspace / "pair-screening" / ".ipynb_checkpoints" / "screening-checkpoint.ipynb",
        _notebook("x = 2\n"),
    )
    _write(workspace / "wbm-dataset" / "summary.txt", "dataset row\n")
    _write(workspace / "wbm-dataset" / "step_1.json.bz2", b"compressed dataset")
    _write(workspace / "wbm-dataset" / "README.txt", "source documentation\n")

    candidates, exclusions = module.discover_candidates(workspace)

    by_path = {item.source_path: item for item in candidates}
    assert by_path["pair-screening/screening.ipynb"].kind == "notebook"
    checkpoint = by_path["pair-screening/.ipynb_checkpoints/screening-checkpoint.ipynb"]
    assert checkpoint.is_revision is True
    assert "revisions" in module.destination_for(checkpoint).parts
    assert "wbm-dataset/README.txt" in by_path
    excluded_paths = {item.source_path for item in exclusions}
    assert "wbm-dataset/summary.txt" in excluded_paths
    assert "wbm-dataset/step_1.json.bz2" in excluded_paths


def test_redaction_preserves_notebook_outputs(tmp_path):
    module = _load_module()
    family = next(item for item in module.FAMILIES if item.source_name == "screen-antiperovskite")
    path = tmp_path / "mpset-test.ipynb"
    result = {
        "output_type": "execute_result",
        "execution_count": 1,
        "metadata": {},
        "data": {"text/plain": ["scientific result"]},
    }
    test_credential = "credential-value-" + "123456"
    raw = _notebook(
        f'with MPRester("{test_credential}") as mpr:\n    pass\n',
        outputs=[result],
    )
    candidate = module.Candidate(
        path=path,
        source_path="screen-antiperovskite/mpset-test.ipynb",
        family=family,
        kind="notebook",
        is_revision=False,
    )

    curated, transformations = module.redact_notebook(candidate, raw)

    before = json.loads(raw)
    after = json.loads(curated)
    assert after["cells"][0]["outputs"] == before["cells"][0]["outputs"]
    assert after["cells"][0]["execution_count"] == 1
    assert test_credential not in curated.decode()
    assert "MPRester()" in curated.decode()
    assert transformations == ["credential-redaction"]


def test_curate_aliases_exact_bytes_but_keeps_distinct_revision(tmp_path):
    module = _load_module()
    workspace = tmp_path / "HC"
    repo = workspace / "ss-screen"
    primary = _notebook("x = 1\n")
    _write(workspace / "pair-screening" / "screening.ipynb", primary)
    _write(
        workspace / "pair-screening" / ".ipynb_checkpoints" / "screening-checkpoint.ipynb",
        primary,
    )
    _write(workspace / "pair-screening" / "analysis.ipynb", _notebook("x = 2\n"))
    _write(
        workspace / "pair-screening" / ".ipynb_checkpoints" / "analysis-checkpoint.ipynb",
        _notebook("x = 3\n"),
    )

    manifest = module.curate(workspace, repo, "2026-07-21", write=True)

    records = {row["source_path"]: row for row in manifest["artifacts"]}
    duplicate = records["pair-screening/.ipynb_checkpoints/screening-checkpoint.ipynb"]
    assert duplicate["status"] == "alias"
    assert duplicate["alias_of"] == "pair-screening/screening.ipynb"
    revision = records["pair-screening/.ipynb_checkpoints/analysis-checkpoint.ipynb"]
    assert revision["status"] == "stored"
    assert "/revisions/" in revision["curated_path"]
    assert (repo / revision["curated_path"]).is_file()


def test_manifest_records_redaction_exclusions_counts_and_indexes(tmp_path):
    module = _load_module()
    workspace = tmp_path / "HC"
    repo = workspace / "ss-screen"
    result = {
        "output_type": "execute_result",
        "execution_count": 1,
        "metadata": {},
        "data": {"text/plain": ["gap = 0.31 eV"]},
    }
    test_credential = "credential-value-" + "123456"
    _write(
        workspace / "screen-antiperovskite" / "mpset-test.ipynb",
        _notebook(f'mpr = MPRester("{test_credential}")\n', outputs=[result]),
    )
    _write(workspace / "wbm-dataset" / "README.txt", "WBM source documentation\n")
    _write(workspace / "wbm-dataset" / "summary.txt", "large dataset row\n")

    manifest = module.curate(workspace, repo, "2026-07-21", write=True)

    records = {row["source_path"]: row for row in manifest["artifacts"]}
    redacted = records["screen-antiperovskite/mpset-test.ipynb"]
    assert redacted["status"] == "redacted"
    assert redacted["source_sha256"] != redacted["curated_sha256"]
    assert redacted["outputs_preserved"] is True
    assert redacted["transformations"] == ["credential-redaction"]
    assert records["wbm-dataset/summary.txt"]["status"] == "excluded"
    assert manifest["counts"] == {"alias": 0, "excluded": 1, "redacted": 1, "stored": 1}
    assert (repo / "references" / "README.md").is_file()
    assert (repo / "references" / "screen-antiperovskite" / "README.md").is_file()


def test_validate_archive_accepts_manifest_and_rejects_tampering(tmp_path):
    module = _load_module()
    workspace = tmp_path / "HC"
    repo = workspace / "ss-screen"
    _write(workspace / "pair-screening" / "screening.ipynb", _notebook("x = 1\n"))
    manifest = module.curate(workspace, repo, "2026-07-21", write=True)

    module.validate_archive(repo / "references", manifest)

    record = next(item for item in manifest["artifacts"] if item["status"] == "stored")
    (repo / record["curated_path"]).write_text("tampered\n")
    with pytest.raises(module.CurationError, match="hash"):
        module.validate_archive(repo / "references", manifest)


def test_cli_dry_run_reports_counts_without_writing(tmp_path, capsys):
    module = _load_module()
    workspace = tmp_path / "HC"
    repo = workspace / "ss-screen"
    _write(workspace / "pair-screening" / "screening.ipynb", _notebook("x = 1\n"))

    result = module.main(
        [
            "--workspace-root",
            str(workspace),
            "--repo-root",
            str(repo),
            "--snapshot-date",
            "2026-07-21",
            "--dry-run",
        ]
    )

    assert result == 0
    assert not (repo / "references").exists()
    report = json.loads(capsys.readouterr().out)
    assert report["counts"]["stored"] == 1


def test_manifest_records_policy_provenance_and_pruned_directories(tmp_path):
    module = _load_module()
    workspace = tmp_path / "HC"
    repo = workspace / "ss-screen"
    _write(workspace / "mp-condense" / "condense.py", "def processone():\n    pass\n")
    _write(workspace / "mp-condense" / "structures" / "mp-1.json", "{}\n")

    manifest = module.curate(workspace, repo, "2026-07-21", write=False)

    assert manifest["policy"]["canonical_implementation"] == "src/ssscreen"
    assert manifest["policy"]["notebook_outputs"] == "preserved"
    assert manifest["redistribution_basis"] == "user-confirmed-2026-07-21"
    record = next(item for item in manifest["artifacts"] if item["status"] == "stored")
    assert record["snapshot_date"] == "2026-07-21"
    assert record["license_status"] == "user-authorized-unspecified"
    assert record["source_git_head"] is None
    assert record["source_git_dirty"] is None
    assert isinstance(record["known_defects"], list)
    assert isinstance(record["portability_notes"], list)
    assert isinstance(record["external_dependencies"], list)
    excluded = {item["source_path"]: item for item in manifest["artifacts"]}
    assert excluded["mp-condense/structures/"]["status"] == "excluded"
    assert excluded["mp-condense/structures/"]["reason"] == "generated structure archive"


def test_cli_write_mode_validates_and_rejects_stale_files(tmp_path):
    module = _load_module()
    workspace = tmp_path / "HC"
    repo = workspace / "ss-screen"
    _write(workspace / "pair-screening" / "screening.ipynb", _notebook("x = 1\n"))
    _write(repo / "references" / "stale.bin", b"stale")

    with pytest.raises(module.CurationError, match="unmanifested"):
        module.main(
            [
                "--workspace-root",
                str(workspace),
                "--repo-root",
                str(repo),
                "--snapshot-date",
                "2026-07-21",
            ]
        )
