"""Barebones, reusable UI widgets for SwissKnife."""
from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QColor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
    QLabel,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QComboBox,
    QTextEdit,
    QFileDialog,
    QColorDialog,
    QInputDialog,
    QMessageBox,
)

from ..core.tool import Param
from ..core.settings import settings


# =============================================================================
# 1. File List & Drop Zone Widget
# =============================================================================

class FileListWidget(QWidget):
    """File table supporting drag-and-drop, individual file selection, and folder scanning."""

    files_changed = Signal(list)

    def __init__(self, accepts: list[str] | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.accepts = accepts or ["*.*"]
        self._files: list[Path] = []
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header info
        info_label = QLabel(f"Accepted: {', '.join(self.accepts)}")
        info_label.setStyleSheet("color: gray;")
        layout.addWidget(info_label)

        # Table
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Name", "Size", "Path"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAcceptDrops(True)
        self.setAcceptDrops(True)
        layout.addWidget(self.table)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_add_files = QPushButton("Add Files...")
        self.btn_add_folder = QPushButton("Add Folder...")
        self.btn_remove = QPushButton("Remove Selected")
        self.btn_clear = QPushButton("Clear All")

        self.btn_add_files.clicked.connect(self._on_add_files)
        self.btn_add_folder.clicked.connect(self._on_add_folder)
        self.btn_remove.clicked.connect(self._on_remove_selected)
        self.btn_clear.clicked.connect(self.clear_files)

        btn_layout.addWidget(self.btn_add_files)
        btn_layout.addWidget(self.btn_add_folder)
        btn_layout.addWidget(self.btn_remove)
        btn_layout.addWidget(self.btn_clear)
        layout.addLayout(btn_layout)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        paths: list[Path] = []
        for url in urls:
            p = Path(url.toLocalFile())
            if p.is_dir():
                paths.extend(self._scan_folder(p))
            elif p.is_file():
                paths.append(p)
        self.add_paths(paths)
        event.acceptProposedAction()

    def _matches_filter(self, path: Path) -> bool:
        if "*.*" in self.accepts or "*" in self.accepts:
            return True
        name = path.name.lower()
        return any(fnmatch.fnmatch(name, pat.lower()) for pat in self.accepts)

    def _scan_folder(self, folder: Path) -> list[Path]:
        found: list[Path] = []
        try:
            for item in folder.rglob("*"):
                if item.is_file() and self._matches_filter(item):
                    found.append(item)
        except Exception:
            pass
        return found

    def _on_add_files(self) -> None:
        ext_filter = "Accepted Files (" + " ".join(self.accepts) + ");;All Files (*.*)"
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files", "", ext_filter)
        if files:
            self.add_paths([Path(f) for f in files])

    def _on_add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Scan")
        if folder:
            paths = self._scan_folder(Path(folder))
            self.add_paths(paths)

    def _on_remove_selected(self) -> None:
        selected_rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()), reverse=True)
        for r in selected_rows:
            if 0 <= r < len(self._files):
                self._files.pop(r)
        self._refresh_table()
        self.files_changed.emit(self._files)

    def add_paths(self, paths: list[Path]) -> None:
        added = False
        for p in paths:
            if p.is_file() and self._matches_filter(p) and p not in self._files:
                self._files.append(p)
                added = True
        if added:
            self._refresh_table()
            self.files_changed.emit(self._files)

    def clear_files(self) -> None:
        self._files.clear()
        self._refresh_table()
        self.files_changed.emit(self._files)

    def _refresh_table(self) -> None:
        self.table.setRowCount(len(self._files))
        for row, f in enumerate(self._files):
            try:
                sz = f.stat().st_size
                sz_str = f"{sz // 1024} KB" if sz > 1024 else f"{sz} B"
            except Exception:
                sz_str = "-"

            item_name = QTableWidgetItem(f.name)
            item_size = QTableWidgetItem(sz_str)
            item_path = QTableWidgetItem(str(f.parent))

            item_size.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            self.table.setItem(row, 0, item_name)
            self.table.setItem(row, 1, item_size)
            self.table.setItem(row, 2, item_path)

    def get_files(self) -> list[Path]:
        return list(self._files)


# =============================================================================
# 2. Dynamic Parameter Form Widget
# =============================================================================

class ParamFormWidget(QWidget):
    """Renders declarative Param items into standard Qt input controls."""

    def __init__(self, params: list[Param], parent: QWidget | None = None):
        super().__init__(parent)
        self.params = params
        self._inputs: dict[str, QWidget] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        for p in self.params:
            widget = self._create_control_for_param(p)
            self._inputs[p.key] = widget
            label = QLabel(p.label + (f" ({p.suffix})" if p.suffix and p.kind not in ("int", "float") else "") + ":")
            if p.help:
                label.setToolTip(p.help)
                widget.setToolTip(p.help)
            layout.addRow(label, widget)

    def _create_control_for_param(self, p: Param) -> QWidget:
        if p.kind == "choice":
            combo = QComboBox()
            for c in p.choices:
                combo.addItem(str(c), c)
            if p.default is not None:
                idx = combo.findData(p.default)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            return combo

        elif p.kind == "int":
            spin = QSpinBox()
            spin.setRange(int(p.minimum if p.minimum is not None else 0),
                           int(p.maximum if p.maximum is not None else 1_000_000))
            if p.step:
                spin.setSingleStep(int(p.step))
            if p.suffix:
                spin.setSuffix(f" {p.suffix}")
            if p.default is not None:
                spin.setValue(int(p.default))
            return spin

        elif p.kind == "float":
            dspin = QDoubleSpinBox()
            dspin.setRange(float(p.minimum if p.minimum is not None else 0.0),
                            float(p.maximum if p.maximum is not None else 1_000_000.0))
            if p.step:
                dspin.setSingleStep(float(p.step))
            if p.suffix:
                dspin.setSuffix(f" {p.suffix}")
            if p.default is not None:
                dspin.setValue(float(p.default))
            return dspin

        elif p.kind == "bool":
            check = QCheckBox()
            check.setChecked(bool(p.default))
            return check

        elif p.kind == "multiline":
            tedit = QTextEdit()
            tedit.setMaximumHeight(80)
            if p.placeholder:
                tedit.setPlaceholderText(p.placeholder)
            if p.default:
                tedit.setPlainText(str(p.default))
            return tedit

        elif p.kind == "color":
            container = QWidget()
            h_layout = QHBoxLayout(container)
            h_layout.setContentsMargins(0, 0, 0, 0)
            line = QLineEdit(str(p.default or "#FFFFFF"))
            btn_pick = QPushButton("Pick...")

            def on_pick():
                col = QColorDialog.getColor(QColor(line.text()), self, "Select Color")
                if col.isValid():
                    line.setText(col.name().upper())

            btn_pick.clicked.connect(on_pick)
            h_layout.addWidget(line)
            h_layout.addWidget(btn_pick)
            container.line_edit = line  # type: ignore
            return container

        else:  # Text
            line = QLineEdit()
            if p.placeholder:
                line.setPlaceholderText(p.placeholder)
            if p.default:
                line.setText(str(p.default))
            return line

    def get_values(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for p in self.params:
            w = self._inputs.get(p.key)
            if w is None:
                continue

            if p.kind == "choice":
                values[p.key] = w.currentData()  # type: ignore
            elif p.kind == "int":
                values[p.key] = w.value()  # type: ignore
            elif p.kind == "float":
                values[p.key] = w.value()  # type: ignore
            elif p.kind == "bool":
                values[p.key] = w.isChecked()  # type: ignore
            elif p.kind == "multiline":
                values[p.key] = w.toPlainText()  # type: ignore
            elif p.kind == "color":
                values[p.key] = w.line_edit.text()  # type: ignore
            else:
                values[p.key] = w.text()  # type: ignore

        return values

    def set_values(self, values: dict[str, Any]) -> None:
        for p in self.params:
            if p.key not in values:
                continue
            val = values[p.key]
            w = self._inputs.get(p.key)
            if w is None:
                continue

            if p.kind == "choice":
                idx = w.findData(val)  # type: ignore
                if idx >= 0:
                    w.setCurrentIndex(idx)  # type: ignore
            elif p.kind == "int":
                w.setValue(int(val))  # type: ignore
            elif p.kind == "float":
                w.setValue(float(val))  # type: ignore
            elif p.kind == "bool":
                w.setChecked(bool(val))  # type: ignore
            elif p.kind == "multiline":
                w.setPlainText(str(val))  # type: ignore
            elif p.kind == "color":
                w.line_edit.setText(str(val))  # type: ignore
            else:
                w.setText(str(val))  # type: ignore


# =============================================================================
# 3. Preset Selector & Manager Widget
# =============================================================================

class PresetWidget(QWidget):
    """Presets dropdown allowing saving, loading, and deleting parameter configurations."""

    preset_loaded = Signal(dict)

    def __init__(self, tool_id: str, form_widget: ParamFormWidget, parent: QWidget | None = None):
        super().__init__(parent)
        self.tool_id = tool_id
        self.form_widget = form_widget
        self._init_ui()
        self.refresh_presets()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Presets:"))
        self.combo = QComboBox()
        self.combo.currentIndexChanged.connect(self._on_preset_selected)
        layout.addWidget(self.combo, 1)

        self.btn_save = QPushButton("Save Current...")
        self.btn_save.clicked.connect(self._on_save_preset)
        layout.addWidget(self.btn_save)

        self.btn_delete = QPushButton("Delete")
        self.btn_delete.clicked.connect(self._on_delete_preset)
        layout.addWidget(self.btn_delete)

    def refresh_presets(self) -> None:
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItem("-- Select Preset --", None)

        saved = settings.list_presets(self.tool_id)
        for name in saved:
            self.combo.addItem(name, name)

        self.combo.blockSignals(False)

    def _on_preset_selected(self, index: int) -> None:
        name = self.combo.currentData()
        if not name:
            return
        preset_data = settings.get_preset(self.tool_id, name)
        if preset_data:
            self.form_widget.set_values(preset_data)
            self.preset_loaded.emit(preset_data)

    def _on_save_preset(self) -> None:
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset Name:")
        if ok and name.strip():
            name = name.strip()
            data = self.form_widget.get_values()
            settings.save_preset(self.tool_id, name, data)
            self.refresh_presets()
            idx = self.combo.findData(name)
            if idx >= 0:
                self.combo.setCurrentIndex(idx)

    def _on_delete_preset(self) -> None:
        name = self.combo.currentData()
        if not name:
            return
        confirm = QMessageBox.question(
            self,
            "Delete Preset",
            f"Are you sure you want to delete preset '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            settings.delete_preset(self.tool_id, name)
            self.refresh_presets()

