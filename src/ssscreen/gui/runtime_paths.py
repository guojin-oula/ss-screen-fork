"""Portable WSL environment path handling for SS-Screen GUI.

Scientific results belong to the active project; virtual environments belong
exclusively to the local machine.  No WSL environment path is stored in a
portable .ssproject container.
"""

from __future__ import annotations

from pathlib import Path, PureWindowsPath


def normalize_wsl_path(value: str) -> str:
    """Accept a WSL absolute path or a Windows drive path and return WSL form.

    Examples:
        C:\\Users\\Lenovo\\ss-screen-latest\\.venv\\bin\\activate
        -> /mnt/c/Users/Lenovo/ss-screen-latest/.venv/bin/activate
    """
    text = value.strip()
    if not text or any(char in text for char in "\n\r\x00"):
        raise ValueError("请输入有效的绝对路径")
    if text.startswith("/"):
        return text
    if len(text) >= 3 and text[1] == ":" and text[2] in ("\\", "/"):
        windows = PureWindowsPath(text)
        drive = windows.drive[:1].lower()
        if not drive.isascii() or not drive.isalpha():
            raise ValueError("Windows盘符无效")
        suffix = "/".join(windows.parts[1:])
        return f"/mnt/{drive}/{suffix}" if suffix else f"/mnt/{drive}"
    raise ValueError("请使用/mnt/c/...或C:\\...形式的绝对路径")


def detect_checkout_venv(app_file: Path, environment: str) -> str:
    """Find a venv in the GUI's source checkout; return '' if unavailable.

    This works when the Windows GUI was installed editable from a source tree.
    A GUI installed from a wheel may need manual paths in Connection settings.
    """
    if environment not in (".venv", ".venv-mlp"):
        raise ValueError("未知虚拟环境类型")
    app_file = Path(app_file).resolve()
    try:
        checkout = app_file.parents[3]
    except IndexError:
        return ""
    expected = checkout / "src" / "ssscreen" / "gui" / app_file.name
    activate = checkout / environment / "bin" / "activate"
    if expected.is_file() and activate.is_file():
        return normalize_wsl_path(str(activate))
    return ""
