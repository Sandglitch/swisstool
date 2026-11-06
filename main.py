"""Main application entry point for SwissKnife."""
import sys
from PySide6.QtWidgets import QApplication

from swissknife.core.registry import registry
from swissknife.ui.main_window import MainWindow


def main():
    # 1. Discover all tools in the swissknife.tools package
    registry.discover("swissknife.tools")

    # 2. Initialize Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("SwissKnife")
    app.setOrganizationName("SwissKnifeTool")

    # 3. Create and show main window
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

