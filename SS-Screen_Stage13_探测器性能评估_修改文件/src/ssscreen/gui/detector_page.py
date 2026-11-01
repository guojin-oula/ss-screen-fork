"""Stage 13 demonstration-oriented detector application assessment page."""

from __future__ import annotations

import html
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget,
)

from ..detector import (
    BAND_PRESETS_UM, DEFAULT_TARGET_UM, DEMO_DEVICE_ROWS, DEMO_ROWS, assess_rows, export_rows,
    index_measurements, read_csv,
)


class DetectorAssessmentPage(QWidget):
    """Read real Stage 12 evidence; show clearly marked demo data on request."""

    COLUMNS = (
        ("candidate_id", "候选ID"),
        ("comp_a", "端元A"),
        ("comp_b", "端元B"),
        ("fraction_b", "组分x"),
        ("gap_eV", "带隙(eV)"),
        ("cutoff_um", "截止波长(μm)"),
        ("band_match", "目标波段"),
        ("classification", "稳定性推荐"),
        ("responsivity_A_W", "响应率(A/W)"),
        ("dark_current_A", "暗电流(A)"),
        ("nep_W_sqrtHz", "NEP(W/√Hz)"),
        ("detectivity_jones", "D*(Jones)"),
        ("rise_time_ms", "上升时间(ms)"),
    )

    def __init__(self, project_provider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_provider = project_provider
        self._results: list[dict[str, object]] = []
        self._source_rows: list[dict[str, str]] = []
        self._demo_mode = False
        self._setup()
        self.refresh()

    def _setup(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(9)

        title_row = QHBoxLayout()
        title = QLabel("探测器材料应用性能评估")
        title.setObjectName("pageTitle")
        title_row.addWidget(title)
        title_row.addStretch(1)
        status = QLabel("STAGE 13 · 展示 / 预筛")
        status.setObjectName("stateBadge")
        title_row.addWidget(status)
        layout.addLayout(title_row)

        self.warning = QLabel(
            "说明：截止波长由带隙推算；端元线性插值不是合金实测带隙。"
            "响应率、暗电流、NEP、D*、上升时间均需独立器件证据，未提供时显示“—”。"
        )
        self.warning.setWordWrap(True)
        self.warning.setStyleSheet("color:#765316; background:#FFF5DE; padding:8px; border-radius:4px;")
        layout.addWidget(self.warning)

        controls = QGroupBox("评估输入 / 参数")
        form = QFormLayout(controls)
        form.setHorizontalSpacing(10)
        self.recommend_path = QLineEdit("12_recommend/recommendations.csv")
        self.recommend_path.setToolTip("工程根目录下的 Stage 12 推荐候选 CSV")
        form.addRow("候选数据", self.recommend_path)
        self.measurements_path = QLineEdit("13_detector/device_measurements.csv")
        self.measurements_path.setToolTip(
            "可选：按 recommendation_id/pair_index 关联外部器件指标；文件不存在表示没有器件数据"
        )
        form.addRow("器件数据(可选)", self.measurements_path)
        band_row = QHBoxLayout()
        self.band = QComboBox()
        self.band.addItems(BAND_PRESETS_UM)
        self.band.setCurrentIndex(1)
        self.target = QDoubleSpinBox()
        self.target.setDecimals(2)
        self.target.setRange(0.01, 100.0)
        self.target.setSuffix(" μm")
        self.target.setValue(DEFAULT_TARGET_UM)
        self.band.currentTextChanged.connect(self._preset_changed)
        band_row.addWidget(self.band, 1)
        band_row.addWidget(self.target)
        form.addRow("目标波长", band_row)
        layout.addWidget(controls)

        actions = QHBoxLayout()
        for label, handler in (
            ("读取工程结果", self.refresh),
            ("加载内置演示数据", self.load_demo),
            ("重新评估", self.recompute),
            ("导出评估 CSV", self.export),
        ):
            button = QPushButton(label)
            button.clicked.connect(handler)
            actions.addWidget(button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.summary = QLabel("-")
        self.summary.setStyleSheet("font-weight:600; padding:5px 0;")
        layout.addWidget(self.summary)
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels([name for _, name in self.COLUMNS])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(False)
        self.table.setColumnWidth(0, 125)
        self.table.setColumnWidth(1, 115)
        self.table.setColumnWidth(2, 115)
        self.table.setColumnWidth(6, 125)
        self.table.itemSelectionChanged.connect(self._detail)
        layout.addWidget(self.table, 3)

        self.details = QTextBrowser()
        self.details.setMaximumHeight(155)
        self.details.setOpenExternalLinks(False)
        layout.addWidget(self.details, 1)

    def _root(self) -> Path:
        return Path(self.project_provider()).expanduser().resolve()

    def _resolve(self, value: str) -> Path:
        path = Path(value.strip()).expanduser()
        return path if path.is_absolute() else self._root() / path

    def _preset_changed(self, label: str) -> None:
        if label in BAND_PRESETS_UM:
            self.target.setValue(BAND_PRESETS_UM[label])

    def refresh(self) -> None:
        """Switch to current project's real recommendations; never auto-invent data."""
        self._demo_mode = False
        path = self._resolve(self.recommend_path.text())
        if path.is_file():
            try:
                self._source_rows = read_csv(path)
            except (OSError, UnicodeError, ValueError) as exc:
                self._source_rows = []
                self.warning.setText(f"无法读取 Stage 12 结果：{exc}")
        else:
            self._source_rows = []
            self.warning.setText(
                f"尚无 Stage 12 推荐候选：{path}。可点击“加载内置演示数据”预览界面。"
                "演示数据绝不代表真实计算或实测结果。"
            )
        self.recompute()

    def load_demo(self) -> None:
        self._demo_mode = True
        self._source_rows = [dict(item) for item in DEMO_ROWS]
        self.recompute()

    def recompute(self) -> None:
        measurements = index_measurements([dict(r) for r in DEMO_DEVICE_ROWS]) if self._demo_mode else {}
        if not self._demo_mode:
            candidate_file = self._resolve(self.measurements_path.text())
            if candidate_file.is_file():
                try:
                    measurements = index_measurements(read_csv(candidate_file))
                except (OSError, UnicodeError, ValueError) as exc:
                    QMessageBox.warning(self, "器件数据读取失败", str(exc))
        self._results = assess_rows(
            self._source_rows, self.target.value(), measurements,
            data_origin="内置演示（非真实材料）" if self._demo_mode else "工程结果",
        )
        if self._demo_mode:
            self.warning.setText(
                "当前使用虚构演示端元，仅展示计算链路和界面！"
                "端元带隙和全部器件指标均为虚构输入；截止波长由线性插值估算，绝非科研证据。"
            )
        elif self._source_rows:
            self.warning.setText(
                "工程结果模式：使用Stage 12候选。若无实测合金带隙，则使用端元线性插值；"
                "缺失器件参数显示“—”，不自动生成虚构数据。"
            )
        covered = sum(r["band_match"] == "带隙覆盖" for r in self._results)
        device_data = sum(r["device_data_source"] != "未提供" for r in self._results)
        self.summary.setText(
            f"数据来源：{'内置虚构示例' if self._demo_mode else '工程文件'}   |   "
            f"候选 {len(self._results)}   |   带隙覆盖 {covered}   |   有器件数据 {device_data}"
        )
        self.table.setRowCount(len(self._results))
        for i, row in enumerate(self._results):
            for j, (key, _) in enumerate(self.COLUMNS):
                v = row.get(key)
                value = "—" if v is None or v == "" else f"{v:.5g}" if isinstance(v, float) else str(v)
                cell = QTableWidgetItem(value)
                if j == 0:
                    cell.setData(Qt.UserRole, i)
                cell.setToolTip(str(v) if v is not None else "无器件数据/缺失")
                if key == "band_match" and v == "带隙覆盖":
                    cell.setForeground(Qt.darkGreen)
                self.table.setItem(i, j, cell)
        self.details.setHtml("<p>选择一行查看带隙依据、稳定性证据和数据来源。</p>")
        if self._results:
            self.table.selectRow(0)

    def _detail(self) -> None:
        selection = self.table.selectedItems()
        if not selection:
            return
        i = selection[0].row()
        if i >= len(self._results):
            return
        item = self._results[i]
        safe = lambda key: html.escape(
            str(item.get(key) if item.get(key) not in (None, "") else "—")
        )
        self.details.setHtml(
            "<p><b>候选：</b>" + safe("candidate_id")
            + "　<b>带隙来源：</b>" + safe("gap_origin")
            + "　<b>数据类型：</b>" + safe("data_origin") + "</p>"
            + "<p><b>凸包距离(eV/atom)：</b>" + safe("energy_above_hull_eV_per_atom")
            + "　<b>声子状态：</b>" + safe("dynamical_status")
            + "　<b>相稳定性：</b>" + safe("hull_signal") + "</p>"
            + "<p><b>器件指标：</b>" + safe("device_data_source")
            + "；<b>限制：</b>" + safe("caution") + "</p>"
        )

    def export(self) -> None:
        if not self._results:
            QMessageBox.information(self, "暂无结果", "请先读取Stage 12候选或加载演示数据。")
            return
        default = self._root() / "13_detector" / "detector_assessment.csv"
        filename, _ = QFileDialog.getSaveFileName(
            self, "导出探测器预筛结果", str(default), "CSV 文件 (*.csv)"
        )
        if not filename:
            return
        try:
            export_rows(Path(filename), self._results)
        except OSError as exc:
            QMessageBox.critical(self, "导出失败", str(exc))
            return
        QMessageBox.information(self, "导出完成", f"已保存：\n{filename}")
