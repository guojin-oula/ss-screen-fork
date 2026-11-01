"""Project packaging and CI configuration tests."""

from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_package_version_is_consistent():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    package_init = (ROOT / "src" / "ssscreen" / "__init__.py").read_text()

    assert data["project"]["version"] == "1.0"
    assert '__version__ = "1.0"' in package_init


def test_dev_tools_are_uv_dependency_group_not_package_extra():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())

    optional = data["project"].get("optional-dependencies", {})
    assert "dev" not in optional

    dev_group = data["dependency-groups"]["dev"]
    assert "pytest>=7" in dev_group
    assert "ruff" in dev_group
    assert "black" in dev_group


def test_unimplemented_dft_execution_is_not_a_package_extra():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())

    optional = data["project"].get("optional-dependencies", {})
    assert "dft" not in optional


def test_ci_workflow_runs_core_tests_without_all_extras():
    workflow = ROOT / ".github" / "workflows" / "ci.yml"

    text = workflow.read_text()

    assert "uv sync" in text
    assert "uv run pytest" in text
    assert "--all-extras" not in text
    assert "dft" not in text


def test_mlp_extra_pins_validated_mace_runtime():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())

    mlp = data["project"]["optional-dependencies"]["mlp"]
    assert "numpy>=1.26,<2" in mlp
    assert "ase>=3.23,<3.27" in mlp
    assert "torch==2.5.1" in mlp
    assert "matscipy==1.1.1" in mlp
    assert "mace-torch==0.3.14" in mlp


def test_phonon_extra_pins_phonopy_major_version():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())

    phonon = data["project"]["optional-dependencies"]["phonon"]
    assert "phonopy>=4.3,<5" in phonon
    assert "seekpath>=2.1" in phonon
    assert "h5py>=3.10" in phonon
    assert "matplotlib>=3.8" in phonon


def test_mp_extra_pins_tested_phase_diagram_api_contract():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())

    assert data["project"]["optional-dependencies"]["mp"] == ["mp-api>=0.46.4,<0.47"]
