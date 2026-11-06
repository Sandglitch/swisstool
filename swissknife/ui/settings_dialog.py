"""Settings dialog for SwissKnife."""
from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QSpinBox,
    QFileDialog,
    QDialogButtonBox,
    QWidget,
)

from ..core.settings import settings


class SettingsDialog(QDialog):
    """Clean settings dialog for app-wide defaults."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Settings - SwissKnife")
        self.resize(500, 220)
        self._init_ui()
        self._load_values()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()

        # Output folder
        folder_container = QWidget()
        f_layout = QHBoxLayout(folder_container)
        f_layout.setContentsMargins(0, 0, 0, 0)
        self.edit_output_dir = QLineEdit()
        self.edit_output_dir.setPlaceholderText("(Default: Same folder as input files)")
        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._on_browse_output_dir)
        f_layout.addWidget(self.edit_output_dir)
        f_layout.addWidget(btn_browse)
        form.addRow("Default Output Folder:", folder_container)

        # Overwrite
        self.check_overwrite = QCheckBox("Overwrite existing files without renaming")
        form.addRow("File Collisions:", self.check_overwrite)

        # Workers
        self.spin_workers = QSpinBox()
        self.spin_workers.setRange(1, 16)
        self.spin_workers.setValue(4)
        form.addRow("Worker Threads:", self.spin_workers)

        layout.addLayout(form)
        layout.addStretch()

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self._on_save)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _load_values(self) -> None:
        self.edit_output_dir.setText(str(settings.get("default_output_dir", "")))
        self.check_overwrite.setChecked(bool(settings.get("overwrite", False)))
        self.spin_workers.setValue(int(settings.get("max_workers", 4)))

    def _on_browse_output_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Default Output Directory")
        if folder:
            self.edit_output_dir.setText(folder)

    def _on_save(self) -> None:
        settings.set("default_output_dir", self.edit_output_dir.text().strip())
        settings.set("overwrite", self.check_overwrite.isChecked())
        settings.set("max_workers", self.spin_workers.value())
        self.accept()

