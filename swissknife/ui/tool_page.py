"""Generic Tool Page dynamically rendered from tool metadata."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QLabel,
    QPushButton,
    QProgressBar,
    QPlainTextEdit,
    QMessageBox,
    QGroupBox,
)

from ..core.tool import Tool, RunResult
from ..core.runner import ToolWorker
from .widgets import FileListWidget, ParamFormWidget, PresetWidget


class ToolPage(QWidget):
    """Dynamic GUI page for an individual SwissKnife tool."""

    def __init__(self, tool: Tool, parent: QWidget | None = None):
        super().__init__(parent)
        self.tool = tool
        self._worker: ToolWorker | None = None
        self._last_outputs: list[Path] = []
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # 1. Header (Title + Description)
        header_widget = QWidget()
        h_layout = QVBoxLayout(header_widget)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(2)

        title_label = QLabel(self.tool.name)
        title_font = title_label.font()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        h_layout.addWidget(title_label)

        if self.tool.description:
            desc_label = QLabel(self.tool.description)
            desc_label.setStyleSheet("color: #555;")
            h_layout.addWidget(desc_label)

        main_layout.addWidget(header_widget)

        # 2. Main content splitter (Files on left, Parameters on right)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel: Files
        files_box = QGroupBox("Input Files")
        files_layout = QVBoxLayout(files_box)
        self.file_list = FileListWidget(accepts=self.tool.accepts)
        self.file_list.files_changed.connect(self._on_files_changed)
        files_layout.addWidget(self.file_list)
        splitter.addWidget(files_box)

        # Right panel: Parameters & Presets
        params_box = QGroupBox("Options")
        params_layout = QVBoxLayout(params_box)

        # Presets at the top of parameters
        self.param_form = ParamFormWidget(self.tool.params)
        self.preset_widget = PresetWidget(self.tool.id, self.param_form)
        params_layout.addWidget(self.preset_widget)

        params_layout.addWidget(self.param_form)
        params_layout.addStretch()
        splitter.addWidget(params_box)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        main_layout.addWidget(splitter, 2)

        # 3. Actions & Progress Bar
        action_bar = QHBoxLayout()

        self.btn_run = QPushButton(f"Run {self.tool.name}")
        self.btn_run.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        self.btn_run.clicked.connect(self._on_run_clicked)

        self.btn_dry_run = QPushButton("Preview / Dry Run")
        self.btn_dry_run.clicked.connect(self._on_dry_run_clicked)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)

        self.btn_open_folder = QPushButton("Open Output Folder")
        self.btn_open_folder.setEnabled(False)
        self.btn_open_folder.clicked.connect(self._on_open_output_folder)

        action_bar.addWidget(self.btn_run)
        action_bar.addWidget(self.btn_dry_run)
        action_bar.addWidget(self.btn_cancel)
        action_bar.addStretch()
        action_bar.addWidget(self.btn_open_folder)
        main_layout.addLayout(action_bar)

        # Progress bar & status label
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        main_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready.")
        main_layout.addWidget(self.status_label)

        # 4. Log / Output Console
        log_box = QGroupBox("Output & Log")
        log_layout = QVBoxLayout(log_box)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(140)
        log_layout.addWidget(self.log_view)
        main_layout.addWidget(log_box, 1)

    def _on_files_changed(self, files: list[Path]) -> None:
        self.status_label.setText(f"{len(files)} file(s) selected.")

    def _execute(self, is_dry_run: bool) -> None:
        files = self.file_list.get_files()
        if self.tool.requires_files and not files:
            QMessageBox.warning(self, "No Files", "Please add one or more files to process.")
            return

        params = self.param_form.get_values()
        self.log_view.clear()
        self.progress_bar.setValue(0)
        self.btn_run.setEnabled(False)
        self.btn_dry_run.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_open_folder.setEnabled(False)

        self._worker = ToolWorker(self.tool, files, params, is_dry_run=is_dry_run)
        self._worker.progress_signal.connect(self._on_worker_progress)
        self._worker.log_signal.connect(self._on_worker_log)
        self._worker.finished_signal.connect(self._on_worker_finished)
        self._worker.failed_signal.connect(self._on_worker_failed)
        self._worker.cancelled_signal.connect(self._on_worker_cancelled)
        self._worker.start()

    def _on_run_clicked(self) -> None:
        self._execute(is_dry_run=False)

    def _on_dry_run_clicked(self) -> None:
        self._execute(is_dry_run=True)

    def _on_cancel_clicked(self) -> None:
        if self._worker:
            self.status_label.setText("Cancelling...")
            self._worker.cancel()

    def _on_worker_progress(self, done: int, total: int, msg: str) -> None:
        if total > 0:
            pct = int(done / total * 100)
            self.progress_bar.setValue(pct)
        if msg:
            self.status_label.setText(msg)

    def _on_worker_log(self, text: str) -> None:
        self.log_view.appendPlainText(text)

    def _on_worker_finished(self, result: RunResult) -> None:
        self.btn_run.setEnabled(True)
        self.btn_dry_run.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setValue(100)
        self._last_outputs = result.outputs

        if result.outputs:
            self.btn_open_folder.setEnabled(True)

        if result.text:
            self.log_view.appendPlainText(result.text)

        msg = result.message or "Completed successfully."
        self.status_label.setText(msg)

    def _on_worker_failed(self, error_msg: str) -> None:
        self.btn_run.setEnabled(True)
        self.btn_dry_run.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.status_label.setText(f"Error: {error_msg}")

    def _on_worker_cancelled(self) -> None:
        self.btn_run.setEnabled(True)
        self.btn_dry_run.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.status_label.setText("Cancelled.")

    def _on_open_output_folder(self) -> None:
        if not self._last_outputs:
            return
        folder = self._last_outputs[0].parent
        if folder.exists():
            if os.name == "nt":
                subprocess.Popen(["explorer", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])

