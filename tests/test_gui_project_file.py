from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from ssscreen.gui.project_file import create_project_file, extract_project_file


def test_project_file_round_trip_and_hash_validation(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    (root / "01_dataset").mkdir(parents=True)
    (root / "10_phonon" / "results").mkdir(parents=True)
    (root / "01_dataset" / "input.json").write_text('{"formula":"CaSe"}', encoding="utf-8")
    (root / "10_phonon" / "results" / "band.csv").write_text("q,f\n0,1\n", encoding="utf-8")
    (root / "notes.txt").write_text("not a stage artifact", encoding="utf-8")

    project_file = tmp_path / "demo.ssproject"
    manifest = create_project_file(root, project_file, project_settings={"device": "cpu"})
    assert manifest["artifact_count"] == 2

    extracted = tmp_path / "opened"
    extract_project_file(project_file, extracted)
    assert (extracted / "01_dataset" / "input.json").read_text(
        encoding="utf-8"
    ) == '{"formula":"CaSe"}'
    assert not (extracted / "notes.txt").exists()
    assert json.loads((extracted / ".ssscreen" / "project.json").read_text(encoding="utf-8"))[
        "settings"
    ] == {"device": "cpu"}


def test_project_file_rejects_tampered_manifest(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    (root / "12_recommend").mkdir(parents=True)
    (root / "12_recommend" / "report.md").write_text("ok", encoding="utf-8")
    source = tmp_path / "source.ssproject"
    create_project_file(root, source)

    tampered = tmp_path / "tampered.ssproject"
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(tampered, "w") as changed:
        for member in original.infolist():
            payload = original.read(member)
            if member.filename == "artifacts/12_recommend/report.md":
                payload = b"changed"
            changed.writestr(member, payload)

    with pytest.raises(ValueError, match="checksum mismatch"):
        extract_project_file(tampered, tmp_path / "opened")
