"""Barebones, reusable UI widgets for SwissKnife."""
from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any

from PIL import Image

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QColor, QPixmap, QImage
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
    QSplitter,
    QGroupBox,
)

from ..core.tool import Tool, Param
from ..core.settings import settings


def pil_to_pixmap(im: Image.Image) -> QPixmap:
    """Convert a PIL Image directly to a QPixmap in memory."""
    if im.mode == "RGBA":
        data = im.tobytes("raw", "RGBA")
        qim = QImage(data, im.width, im.height, QImage.Format.Format_RGBA8888)
    elif im.mode == "RGB":
        data = im.tobytes("raw", "RGB")
        qim = QImage(data, im.width, im.height, im.width * 3, QImage.Format.Format_RGB888)
    else:
        rgb = im.convert("RGBA")
        data = rgb.tobytes("raw", "RGBA")
        qim = QImage(data, rgb.width, rgb.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qim)


# =============================================================================
# 1. File List & Drop Zone Widget
# =============================================================================

class FileListWidget(QWidget):
    """File table supporting drag-and-drop, individual file selection, and folder scanning."""

    files_changed = Signal(list)
    file_selected = Signal(object)  # Path or None

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
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
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
        if self._files:
            self.table.selectRow(0)
        else:
            self.file_selected.emit(None)

    def _on_table_selection_changed(self) -> None:
        selected = self.table.selectedIndexes()
        if selected:
            row = selected[0].row()
            if 0 <= row < len(self._files):
                self.file_selected.emit(self._files[row])
                return
        self.file_selected.emit(None)

    def add_paths(self, paths: list[Path]) -> None:
        had_files = len(self._files) > 0
        added = False
        for p in paths:
            if p.is_file() and self._matches_filter(p) and p not in self._files:
                self._files.append(p)
                added = True
        if added:
            self._refresh_table()
            self.files_changed.emit(self._files)
            if not had_files and self.table.rowCount() > 0:
                self.table.selectRow(0)

    def clear_files(self) -> None:
        self._files.clear()
        self._refresh_table()
        self.files_changed.emit(self._files)
        self.file_selected.emit(None)

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

    def get_selected_file(self) -> Path | None:
        selected = self.table.selectedIndexes()
        if selected:
            row = selected[0].row()
            if 0 <= row < len(self._files):
                return self._files[row]
        return self._files[0] if self._files else None


# =============================================================================
# 2. Dynamic Parameter Form Widget
# =============================================================================

class ParamFormWidget(QWidget):
    """Renders declarative Param items into standard Qt input controls."""

    values_changed = Signal(dict)

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

    def _emit_changed(self) -> None:
        self.values_changed.emit(self.get_values())

    def _create_control_for_param(self, p: Param) -> QWidget:
        if p.kind == "choice":
            combo = QComboBox()
            for c in p.choices:
                combo.addItem(str(c), c)
            if p.default is not None:
                idx = combo.findData(p.default)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            combo.currentIndexChanged.connect(self._emit_changed)
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
            spin.valueChanged.connect(self._emit_changed)
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
            dspin.valueChanged.connect(self._emit_changed)
            return dspin

        elif p.kind == "bool":
            check = QCheckBox()
            check.setChecked(bool(p.default))
            check.toggled.connect(self._emit_changed)
            return check

        elif p.kind == "multiline":
            tedit = QTextEdit()
            tedit.setMaximumHeight(80)
            if p.placeholder:
                tedit.setPlaceholderText(p.placeholder)
            if p.default:
                tedit.setPlainText(str(p.default))
            tedit.textChanged.connect(self._emit_changed)
            return tedit

        elif p.kind == "color":
            container = QWidget()
            h_layout = QHBoxLayout(container)
            h_layout.setContentsMargins(0, 0, 0, 0)
            line = QLineEdit(str(p.default or "#FFFFFF"))
            line.textChanged.connect(self._emit_changed)
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
            line.textChanged.connect(self._emit_changed)
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


# =============================================================================
# 4. Scalable Image Label
# =============================================================================

class ScalableImageLabel(QLabel):
    """A QLabel that automatically scales its pixmap smoothly to fit its dimensions while preserving aspect ratio."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(100, 100)
        self.setStyleSheet("background: #f7f7f7; border: 1px solid #ddd; border-radius: 4px;")

    def set_pixmap(self, pixmap: QPixmap | None) -> None:
        self._pixmap = pixmap
        self._update_display()

    def _update_display(self) -> None:
        if self._pixmap and not self._pixmap.isNull():
            w = max(10, self.width() - 8)
            h = max(10, self.height() - 8)
            scaled = self._pixmap.scaled(
                w,
                h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            super().setPixmap(scaled)
        else:
            super().clear()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_display()


# =============================================================================
# 5. Image Preview Widget (Side-by-Side Before & After)
# =============================================================================

class ImagePreviewWidget(QGroupBox):
    """Panel showing the image being worked on and real-time preview of changes."""

    def __init__(self, tool: Tool, parent: QWidget | None = None):
        super().__init__("Image Preview", parent)
        self.tool = tool
        self._current_file: Path | None = None
        self._current_params: dict[str, Any] = {}
        self._orig_pixmap: QPixmap | None = None

        # Debounce timer to prevent lag when rapidly tweaking controls
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(120)
        self._debounce_timer.timeout.connect(self._render_preview)

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Top Bar: File info + View mode selector
        top_bar = QHBoxLayout()
        self.lbl_filename = QLabel("No image selected.")
        self.lbl_filename.setStyleSheet("font-weight: bold; color: #333;")
        top_bar.addWidget(self.lbl_filename, 1)

        top_bar.addWidget(QLabel("View:"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItem("Side-by-Side (Before & After)")
        self.combo_mode.addItem("Preview (Changes Only)")
        self.combo_mode.addItem("Original Only")
        self.combo_mode.currentIndexChanged.connect(self._on_view_mode_changed)
        top_bar.addWidget(self.combo_mode)
        layout.addLayout(top_bar)

        # Splitter holding the Before and After views
        self.view_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 1. Left container: Original Image
        self.orig_container = QWidget()
        orig_layout = QVBoxLayout(self.orig_container)
        orig_layout.setContentsMargins(0, 0, 0, 0)
        orig_layout.setSpacing(2)
        self.lbl_orig_info = QLabel("Original")
        self.lbl_orig_info.setStyleSheet("color: #666; font-size: 11px;")
        self.orig_display = ScalableImageLabel()
        orig_layout.addWidget(self.lbl_orig_info)
        orig_layout.addWidget(self.orig_display, 1)
        self.view_splitter.addWidget(self.orig_container)

        # 2. Right container: Preview Changes
        self.prev_container = QWidget()
        prev_layout = QVBoxLayout(self.prev_container)
        prev_layout.setContentsMargins(0, 0, 0, 0)
        prev_layout.setSpacing(2)
        self.lbl_prev_info = QLabel("Preview (Changes)")
        self.lbl_prev_info.setStyleSheet("color: #0b6623; font-weight: bold; font-size: 11px;")
        self.prev_display = ScalableImageLabel()
        prev_layout.addWidget(self.lbl_prev_info)
        prev_layout.addWidget(self.prev_display, 1)
        self.view_splitter.addWidget(self.prev_container)

        self.view_splitter.setStretchFactor(0, 1)
        self.view_splitter.setStretchFactor(1, 1)
        layout.addWidget(self.view_splitter, 1)

    def _on_view_mode_changed(self, index: int) -> None:
        if index == 0:  # Side-by-Side
            self.orig_container.setVisible(True)
            self.prev_container.setVisible(True)
        elif index == 1:  # Changes Only
            self.orig_container.setVisible(False)
            self.prev_container.setVisible(True)
        else:  # Original Only
            self.orig_container.setVisible(True)
            self.prev_container.setVisible(False)

    def set_file(self, file_path: Path | None, current_params: dict[str, Any]) -> None:
        """Set the active file being inspected."""
        self._current_file = file_path
        self._current_params = current_params

        if not file_path or not file_path.exists():
            self.lbl_filename.setText("No image selected.")
            self.lbl_orig_info.setText("Original")
            self.lbl_prev_info.setText("Preview (Changes)")
            self.orig_display.set_pixmap(None)
            self.prev_display.set_pixmap(None)
            return

        self.lbl_filename.setText(f"File: {file_path.name}")

        # Load Original
        try:
            with Image.open(file_path) as im:
                sz = file_path.stat().st_size
                sz_str = f"{sz // 1024} KB" if sz > 1024 else f"{sz} B"
                self.lbl_orig_info.setText(f"Original: {im.width} × {im.height} px ({sz_str})")
                self._orig_pixmap = pil_to_pixmap(im)
                self.orig_display.set_pixmap(self._orig_pixmap)
        except Exception as e:
            self.lbl_orig_info.setText("Original: (Unable to load image)")
            self.orig_display.set_pixmap(None)

        self._debounce_timer.start()

    def update_params(self, params: dict[str, Any]) -> None:
        """Called when user changes parameter form options."""
        self._current_params = params
        if self._current_file:
            self._debounce_timer.start()

    def _render_preview(self) -> None:
        """Generate and update the preview image."""
        if not self._current_file or not self._current_file.exists():
            return

        try:
            preview_im = self.tool.preview(self._current_file, self._current_params)
            if preview_im is not None:
                pix = pil_to_pixmap(preview_im)
                self.prev_display.set_pixmap(pix)
                self.lbl_prev_info.setText(f"Preview: {preview_im.width} × {preview_im.height} px")
            else:
                # If tool didn't modify pixel data, fall back to original
                self.prev_display.set_pixmap(self._orig_pixmap)
                self.lbl_prev_info.setText("Preview: (No visual preview changes)")
        except Exception as e:
            self.lbl_prev_info.setText(f"Preview error: {e}")
            self.prev_display.set_pixmap(None)
