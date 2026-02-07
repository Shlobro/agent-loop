"""
AgentHarness - Autonomous Code Generation GUI

Entry point for the application.
"""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QSettings

from src.gui.main_window import MainWindow
from src.gui.dialogs.startup_directory_dialog import StartupDirectoryDialog


RECENT_WORKING_DIRECTORIES_KEY = "recent_working_directories"
MAX_RECENT_WORKING_DIRECTORIES = 10


def _load_recent_working_directories() -> list[str]:
    """Load recent working directories from Qt settings."""
    settings = QSettings()
    raw = settings.value(RECENT_WORKING_DIRECTORIES_KEY, [])
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(path) for path in raw if str(path).strip()]
    return []


def _save_recent_working_directories(paths: list[str]):
    """Persist recent working directories to Qt settings."""
    settings = QSettings()
    deduped: list[str] = []
    for path in paths:
        normalized = str(path).strip()
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    settings.setValue(RECENT_WORKING_DIRECTORIES_KEY, deduped[:MAX_RECENT_WORKING_DIRECTORIES])


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

    recent_dirs = _load_recent_working_directories()
    startup_dialog = StartupDirectoryDialog(recent_dirs)
    if startup_dialog.exec() == 0:
        sys.exit(0)
    startup_working_directory = startup_dialog.get_selected_directory().strip()
    ordered_recent = [startup_working_directory, *recent_dirs]
    _save_recent_working_directories(ordered_recent)

    # Create and show main window
    window = MainWindow()
    window.initialize_directory_settings(startup_working_directory)
    app.aboutToQuit.connect(window.save_current_working_directory_settings)
    window.show()

    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
