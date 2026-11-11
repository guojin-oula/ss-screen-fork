from pathlib import Path

import pytest

from ssscreen.gui.runtime_paths import detect_checkout_venv, normalize_wsl_path


def test_normalize_wsl_path_from_windows():
    assert normalize_wsl_path(
        r"C:\Users\Lenovo\ss-screen-latest\.venv\bin\activate"
    ) == "/mnt/c/Users/Lenovo/ss-screen-latest/.venv/bin/activate"


def test_normalize_wsl_path_from_linux():
    value = "/mnt/c/Users/Lenovo/ss-screen-latest/.venv-mlp/bin/activate"
    assert normalize_wsl_path(value) == value


@pytest.mark.parametrize("bad", ["", "./.venv/bin/activate", "relative", "\\\\server\\share", "hello\nworld"])
def test_normalize_wsl_path_rejects_invalid(bad):
    with pytest.raises(ValueError):
        normalize_wsl_path(bad)


def test_detect_checkout_venv(tmp_path: Path):
    app = tmp_path / "src" / "ssscreen" / "gui" / "app.py"
    app.parent.mkdir(parents=True)
    app.touch()
    assert detect_checkout_venv(app, ".venv") == ""
    activation = tmp_path / ".venv" / "bin" / "activate"
    activation.parent.mkdir(parents=True)
    activation.touch()
    assert detect_checkout_venv(app, ".venv") == str(activation)
    assert detect_checkout_venv(app, ".venv-mlp") == ""


def test_detect_invalid_venv(tmp_path):
    with pytest.raises(ValueError):
        detect_checkout_venv(tmp_path / "app.py", "unrecognized")
