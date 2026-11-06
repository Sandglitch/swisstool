"""Main application window for SwissKnife."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QStackedWidget,
    QLabel,
    QStatusBar,
    QMessageBox,
)

from ..core.registry import registry
from .tool_page import ToolPage
from .settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    """Main window with category/tool navigation sidebar and dynamic tool host."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SwissKnife")
        self.resize(1150, 750)
        self._tool_pages: dict[str, QWidget] = {}
        self._init_ui()
        self._populate_sidebar()

    def _init_ui(self) -> None:
        # Menus
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")

        settings_action = file_menu.addAction("&Settings...")
        settings_action.triggered.connect(self._open_settings)

        file_menu.addSeparator()
        exit_action = file_menu.addAction("E&xit")
        exit_action.triggered.connect(self.close)

        help_menu = menu_bar.addMenu("&Help")
        about_action = help_menu.addAction("&About SwissKnife")
        about_action.triggered.connect(self._show_about)

        # Central Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(splitter)

        # Sidebar navigation
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(220)
        self.tree.itemSelectionChanged.connect(self._on_tree_selection_changed)
        splitter.addWidget(self.tree)

        # Stacked pages
        self.stack = QStackedWidget()
        splitter.addWidget(self.stack)

        # Default placeholder page
        self.placeholder_page = self._create_placeholder("Select a tool from the sidebar to begin.")
        self.stack.addWidget(self.placeholder_page)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)

        # Status Bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        total_tools = len(registry.all_tools())
        self.status.showMessage(f"SwissKnife | Ready | {total_tools} Tools Available")

    def _create_placeholder(self, text: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: #666; font-size: 13px; line-height: 1.5;")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)
        return widget

    def _populate_sidebar(self) -> None:
        self.tree.clear()
        categories = registry.categories()

        first_tool_item: QTreeWidgetItem | None = None

        for cat_id, cat_label in categories:
            cat_tools = registry.get_by_category(cat_id)
            if not cat_tools:
                # Do not show categories that have no registered tools
                continue

            count = len(cat_tools)
            cat_item = QTreeWidgetItem(self.tree)
            cat_item.setText(0, f"{cat_label} ({count})")
            cat_item.setData(0, Qt.ItemDataRole.UserRole, ("category", cat_id))
            font = cat_item.font(0)
            font.setBold(True)
            cat_item.setFont(0, font)

            for tool in cat_tools:
                tool_item = QTreeWidgetItem(cat_item)
                tool_item.setText(0, tool.name)
                tool_item.setData(0, Qt.ItemDataRole.UserRole, ("tool", tool.id))
                if first_tool_item is None:
                    first_tool_item = tool_item

            cat_item.setExpanded(True)

        if first_tool_item:
            self.tree.setCurrentItem(first_tool_item)

    def _on_tree_selection_changed(self) -> None:
        selected = self.tree.selectedItems()
        if not selected:
            return

        item = selected[0]
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        kind, identifier = data
        if kind == "tool":
            tool = registry.get(identifier)
            if tool:
                if identifier not in self._tool_pages:
                    page = ToolPage(tool)
                    self._tool_pages[identifier] = page
                    self.stack.addWidget(page)
                self.stack.setCurrentWidget(self._tool_pages[identifier])
                self.status.showMessage(f"Active Tool: {tool.name}")

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self)
        dialog.exec()

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About SwissKnife",
            "<b>SwissKnife</b> — Desktop File Toolbox<br>"
            "Version 0.1.0<br><br>"
            "A fast local desktop utility for batch file chores without cloud uploads.<br>"
            "Built with PySide6 & Pillow."
        )
