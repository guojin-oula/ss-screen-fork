from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu")
pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtGui import QFont, QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication, QToolButton  # noqa: E402

from ssscreen.gui.app import MainWindow  # noqa: E402
from ssscreen.gui.appearance import (  # noqa: E402
    DEFAULT_FONT_SIZE,
    FONT_SETTINGS_KEY,
    font_size,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    if os.name == "nt" and not QFontDatabase.families():
        for filename in ("segoeui.ttf", "msyh.ttc", "consola.ttf"):
            QFontDatabase.addApplicationFont(str(Path(os.environ["WINDIR"]) / "Fonts" / filename))
        app.setFont(QFont("Microsoft YaHei UI", DEFAULT_FONT_SIZE))
    return app


def test_font_preference_round_trip_and_layout(qapp, tmp_path: Path) -> None:
    settings = QSettings(str(tmp_path / "display.ini"), QSettings.IniFormat)
    window = MainWindow(str(tmp_path), settings=settings)
    window.resize(1024, 768)
    window.show()
    qapp.processEvents()
    assert window.menuWidget() is None
    assert window.view_button.parentWidget() is window.command_toolbar
    assert window.view_button.defaultAction().menu() is window.view_menu
    assert window.view_action in window.command_toolbar.actions()
    initial_height = window.dashboard.table.rowHeight(0)
    window.font_size_actions[16].trigger()
    qapp.processEvents()
    assert window.dashboard.table.rowHeight(0) > initial_height
    assert window.dashboard.table.rowHeight(0) >= window.dashboard.table.fontMetrics().height()
    assert settings.value(FONT_SETTINGS_KEY, type=int) == 16
    assert "font-size: 10px" not in window.styleSheet()
    assert window.width() == 1024
    assert window.height() == 768
    assert window.inspector_scroll.verticalScrollBar().maximum() > 0
    assert any(button.isVisible() for button in window.command_toolbar.findChildren(QToolButton))
    extension = window.command_toolbar.findChild(QToolButton, "qt_toolbar_ext_button")
    assert extension.isVisible()
    width = window.dashboard.table.columnWidth(1)
    assert window.font_menu.menuAction() in window.view_menu.actions()
    assert window.font_size_actions[16].isChecked()
    assert sum(action.isChecked() for action in window.font_size_actions.values()) == 1
    window.font_size_actions[DEFAULT_FONT_SIZE].trigger()
    window.font_size_actions[16].trigger()
    assert window.dashboard.table.columnWidth(1) == width
    window.close()

    reopened = MainWindow(str(tmp_path), settings=settings)
    assert reopened.font_size_actions[16].isChecked()
    reopened.font_reset_action.trigger()
    assert settings.value(FONT_SETTINGS_KEY, type=int) == DEFAULT_FONT_SIZE
    reopened.close()


def test_late_command_page_inherits_font(qapp, tmp_path: Path) -> None:
    settings = QSettings(str(tmp_path / "display.ini"), QSettings.IniFormat)
    window = MainWindow(str(tmp_path), settings=settings)
    window.font_size_actions[18].trigger()
    window._show_command_page(("stability", "relax"))
    qapp.processEvents()
    page = window._pages[("stability", "relax")]
    assert page.preview.font().pointSizeF() >= 17
    assert page.preview.maximumHeight() > 72
    assert window.structure_results_page.viewer.zoomFactor() == pytest.approx(1.8)
    window.close()


@pytest.mark.parametrize("value, expected", [(None, 10), ("bad", 10), (2, 9), (99, 18)])
def test_invalid_saved_font_is_usable(value: object, expected: int) -> None:
    assert font_size(value) == expected
