"""Result visualization widgets for the desktop workbench."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from pymatgen.core import Composition
from PySide6.QtCore import QPointF, Qt, QUrl
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


def _csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class MatterVizView(QWebEngineView):
    """Offline MatterViz host that accepts local structure files from Python."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(360, 320)
        self._pending: tuple[str, str, str] | None = None
        self._ready = False
        self.loadFinished.connect(self._loaded)
        index = Path(__file__).with_name("matterviz_dist") / "index.html"
        if index.is_file():
            self.load(QUrl.fromLocalFile(str(index.resolve())))
        else:
            self.setHtml("<h3>MatterViz resources are not built.</h3>")

    def _loaded(self, ok: bool) -> None:
        self._ready = ok
        if ok and self._pending:
            content, filename, label = self._pending
            self._pending = None
            self._send(content, filename, label)

    def load_structure(self, path: Path, label: str | None = None) -> None:
        if not path.is_file():
            return
        content = path.read_text(encoding="utf-8", errors="replace")
        payload = (content, path.name, label or path.stem)
        if self._ready:
            self._send(*payload)
        else:
            self._pending = payload

    def _send(self, content: str, filename: str, label: str) -> None:
        arguments = ", ".join(
            json.dumps(value, ensure_ascii=False) for value in (content, filename, label)
        )
        self.page().runJavaScript(f"window.ssScreenLoadStructure({arguments})")


class StructureResultsPage(QWidget):
    """Browse relaxed and generated structures with the embedded MatterViz viewer."""

    def __init__(self, project_provider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_provider = project_provider
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        header = QHBoxLayout()
        title = QLabel("晶体结构可视化")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        refresh = QPushButton("刷新结构")
        refresh.clicked.connect(self.refresh)
        header.addWidget(refresh)
        layout.addLayout(header)

        self.selector = QComboBox()
        self.selector.currentIndexChanged.connect(self._selection_changed)
        layout.addWidget(self.selector)
        self.viewer = MatterVizView()
        self.viewer.setMinimumHeight(460)
        layout.addWidget(self.viewer, 1)
        self.refresh()

    def _root(self) -> Path:
        return Path(self.project_provider()).expanduser().resolve()

    def refresh(self) -> None:
        current = self.selector.currentData()
        self.selector.blockSignals(True)
        self.selector.clear()
        patterns = (
            "07_sqs/structures/**/*.json",
            "08_relax/structures/**/*.json",
            "10_phonon/inputs/**/structures/reference.json",
            "11_phase/relaxation/structures/*.json",
        )
        seen: set[Path] = set()
        for pattern in patterns:
            for path in sorted(self._root().glob(pattern)):
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                label = path.relative_to(self._root()).as_posix()
                self.selector.addItem(label, str(path))
        self.selector.blockSignals(False)
        if current:
            index = self.selector.findData(current)
            if index >= 0:
                self.selector.setCurrentIndex(index)
        self._selection_changed(self.selector.currentIndex())

    def _selection_changed(self, index: int) -> None:
        if index >= 0:
            path = Path(str(self.selector.itemData(index)))
            self.viewer.load_structure(path, self.selector.itemText(index))


class ScaledImage(QLabel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source = QPixmap()
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(360, 280)
        self.setText("尚无图像")

    def set_image(self, path: Path) -> None:
        self._source = QPixmap(str(path)) if path.is_file() else QPixmap()
        self._rescale()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self) -> None:
        if self._source.isNull():
            self.setPixmap(QPixmap())
            self.setText("尚无声子频带/DOS图")
            return
        self.setText("")
        self.setPixmap(
            self._source.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )


class PhononResultsPage(QWidget):
    """Stage 10 summary, generated band/DOS image and linked structure viewer."""

    def __init__(self, project_provider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_provider = project_provider
        self.rows: list[dict[str, str]] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        header = QHBoxLayout()
        title = QLabel("声子谱结果")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        refresh = QPushButton("刷新结果")
        refresh.clicked.connect(self.refresh)
        header.addWidget(refresh)
        root.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        overview = QWidget()
        overview_layout = QVBoxLayout(overview)
        overview_layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Horizontal)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["结构", "角色", "状态", "动力学", "最低频率(THz)", "虚频数", "力覆盖率"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.setMinimumWidth(570)
        header_view = self.table.horizontalHeader()
        for column in range(4):
            header_view.setSectionResizeMode(column, QHeaderView.Stretch)
        for column in range(4, 7):
            header_view.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        splitter.addWidget(self.table)

        self.image = ScaledImage()
        splitter.addWidget(self.image)
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        overview_layout.addWidget(splitter, 1)
        self.tabs.addTab(overview, "频带、DOS 与结果表")

        self.viewer = MatterVizView()
        self.viewer.setMinimumHeight(520)
        self.tabs.addTab(self.viewer, "对应晶体（MatterViz）")
        root.addWidget(self.tabs, 1)
        self.refresh()

    def _root(self) -> Path:
        return Path(self.project_provider()).expanduser().resolve()

    def refresh(self) -> None:
        self.rows = _csv_rows(self._root() / "10_phonon" / "phonon_summary.csv")
        self.table.setRowCount(0)
        keys = (
            "structure_id",
            "structure_role",
            "status",
            "dynamical_status",
            "minimum_mesh_frequency_THz",
            "significant_imaginary_mode_count",
            "force_coverage",
        )
        for row in self.rows:
            position = self.table.rowCount()
            self.table.insertRow(position)
            for column, key in enumerate(keys):
                self.table.setItem(position, column, QTableWidgetItem(row.get(key, "")))
        if self.rows:
            self.table.selectRow(0)

    def _selection_changed(self) -> None:
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return
        row = self.rows[indexes[0].row()]
        phonon_id = row.get("phonon_id", "")
        result_dir = self._root() / "10_phonon" / "results" / phonon_id
        self.image.set_image(result_dir / "phonon_band_dos.png")
        structure = (
            self._root() / "10_phonon" / "inputs" / phonon_id / "structures" / "reference.json"
        )
        self.viewer.load_structure(structure, row.get("structure_id") or phonon_id)


class TernaryHullCanvas(QFrame):
    """Compact ternary composition map colored by energy above hull."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.rows: list[dict[str, str]] = []
        self.elements: list[str] = []
        self.setMinimumSize(430, 390)
        self.setFrameShape(QFrame.StyledPanel)

    def set_rows(self, rows: list[dict[str, str]]) -> None:
        self.rows = rows
        elements: set[str] = set()
        for row in rows:
            try:
                elements.update(Composition(row.get("phase_composition", "")).elements)
            except Exception:
                continue
        self.elements = sorted(str(element) for element in elements)[:3]
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        margin = 48.0
        width = max(10.0, self.width() - 2 * margin)
        height = max(10.0, self.height() - 2 * margin)
        side = min(width, height * 2 / math.sqrt(3))
        triangle_height = side * math.sqrt(3) / 2
        left = (self.width() - side) / 2
        top = (self.height() - triangle_height) / 2
        vertices = [
            QPointF(left, top + triangle_height),
            QPointF(left + side, top + triangle_height),
            QPointF(left + side / 2, top),
        ]
        painter.setPen(QPen(QColor("#59636b"), 1.5))
        painter.setBrush(QColor("#fafafa"))
        painter.drawPolygon(QPolygonF(vertices))
        if len(self.elements) == 3:
            painter.drawText(vertices[0] + QPointF(-24, 22), self.elements[0])
            painter.drawText(vertices[1] + QPointF(8, 22), self.elements[1])
            painter.drawText(vertices[2] + QPointF(-8, -10), self.elements[2])

        for row in self.rows:
            try:
                composition = Composition(row.get("phase_composition", "")).fractional_composition
                fractions = [composition.get_atomic_fraction(element) for element in self.elements]
                if len(fractions) != 3:
                    continue
                point = QPointF(
                    sum(
                        weight * vertex.x()
                        for weight, vertex in zip(fractions, vertices, strict=True)
                    ),
                    sum(
                        weight * vertex.y()
                        for weight, vertex in zip(fractions, vertices, strict=True)
                    ),
                )
                energy = float(row.get("phase_e_above_augmented_hull_eV_per_atom") or 0)
                target = str(row.get("is_target", "")).lower() == "true"
                color = (
                    QColor("#b32424")
                    if target
                    else QColor("#2d7f5e" if energy <= 1e-6 else "#d39b32")
                )
                painter.setPen(QPen(QColor("#ffffff"), 1))
                painter.setBrush(color)
                radius = 7 if target else 5
                painter.drawEllipse(point, radius, radius)
            except Exception:
                continue
        painter.end()


class PhaseResultsPage(QWidget):
    """Stage 11 ternary hull map, entry table and linked MatterViz structure."""

    def __init__(self, project_provider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_provider = project_provider
        self.rows: list[dict[str, str]] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        header = QHBoxLayout()
        title = QLabel("竞争相与凸包结果")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        self.count_label = QLabel("尚无相条目")
        self.count_label.setObjectName("smallLabel")
        header.addWidget(self.count_label)
        header.addStretch(1)
        refresh = QPushButton("刷新结果")
        refresh.clicked.connect(self.refresh)
        header.addWidget(refresh)
        root.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        hull_page = QWidget()
        hull_layout = QVBoxLayout(hull_page)
        hull_layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Horizontal)
        self.canvas = TernaryHullCanvas()
        splitter.addWidget(self.canvas)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["相结构 ID", "组成", "角色", "凸包距离\n(eV/atom)", "目标"]
        )
        self.table.setMinimumWidth(650)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.Stretch)
        header_view.setSectionResizeMode(1, QHeaderView.Fixed)
        header_view.setSectionResizeMode(2, QHeaderView.Fixed)
        header_view.setSectionResizeMode(3, QHeaderView.Fixed)
        header_view.setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 90)
        self.table.setColumnWidth(2, 110)
        self.table.setColumnWidth(3, 125)
        self.table.setColumnWidth(4, 60)
        splitter.addWidget(self.table)
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        hull_layout.addWidget(splitter, 1)
        self.tabs.addTab(hull_page, "凸包与竞争相")
        self.viewer = MatterVizView()
        self.viewer.setMinimumHeight(520)
        self.tabs.addTab(self.viewer, "相结构（MatterViz）")
        root.addWidget(self.tabs, 1)
        self.refresh()

    def _root(self) -> Path:
        return Path(self.project_provider()).expanduser().resolve()

    def refresh(self) -> None:
        self.rows = _csv_rows(self._root() / "11_phase" / "hull_entries.csv")
        self.count_label.setText(f"{len(self.rows)} 个相条目" if self.rows else "尚无相条目")
        self.canvas.set_rows(self.rows)
        self.table.setRowCount(0)
        keys = (
            "phase_structure_id",
            "phase_composition",
            "phase_role",
            "phase_e_above_augmented_hull_eV_per_atom",
            "is_target",
        )
        for row in self.rows:
            position = self.table.rowCount()
            self.table.insertRow(position)
            for column, key in enumerate(keys):
                raw = row.get(key, "")
                display = raw
                if key == "phase_role":
                    display = "目标结构" if raw == "target" else "竞争相"
                elif key == "phase_e_above_augmented_hull_eV_per_atom":
                    try:
                        display = f"{float(raw):.6f}"
                    except ValueError:
                        pass
                elif key == "is_target":
                    display = "是" if raw.lower() == "true" else "否"
                item = QTableWidgetItem(display)
                item.setToolTip(raw)
                self.table.setItem(position, column, item)
        if self.rows:
            self.table.selectRow(0)

    def _selection_changed(self) -> None:
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return
        row = self.rows[indexes[0].row()]
        structure_id = row.get("phase_structure_id", "")
        if str(row.get("is_target", "")).lower() == "true":
            path = self._root() / "08_relax" / "structures" / f"{structure_id}.json"
        else:
            path = self._root() / "11_phase" / "relaxation" / "structures" / f"{structure_id}.json"
        self.viewer.load_structure(path, f"{row.get('phase_composition')} · {structure_id}")
