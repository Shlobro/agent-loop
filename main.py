"""
AgentHarness - Autonomous Code Generation GUI

Entry point for the application.
"""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from src.gui.main_window import MainWindow


def main():
    """Main entry point."""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("AgentHarness")
    app.setOrganizationName("AgentHarness")
    app.setApplicationDisplayName("AgentHarness - Autonomous Code Generator")

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
