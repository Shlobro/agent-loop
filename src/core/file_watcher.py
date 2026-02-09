"""File system watcher for monitoring product-description.md for external changes."""

from pathlib import Path
from PySide6.QtCore import QObject, QFileSystemWatcher, Signal


class DescriptionFileWatcher(QObject):
    """
    Monitor product-description.md for external changes.

    Emits signal when the file is modified externally (not through the app).
    """

    file_changed_externally = Signal(str)  # Emits new content

    def __init__(self, parent=None):
        super().__init__(parent)
        self.watcher = QFileSystemWatcher(self)
        self.watching_path = None
        self.last_known_content = ""
        self._ignore_next_change = False

        # Connect file system watcher signal
        self.watcher.fileChanged.connect(self._on_file_changed)

    def start_watching(self, working_directory: str):
        """Start watching product-description.md in the given directory."""
        if self.watching_path:
            self.stop_watching()

        file_path = Path(working_directory) / "product-description.md"

        # Ensure file exists
        if not file_path.exists():
            try:
                file_path.write_text("", encoding="utf-8")
            except Exception:
                return  # Can't create file, can't watch

        self.watching_path = str(file_path)
        self.last_known_content = self._read_file_content()

        # Start watching
        if self.watching_path:
            self.watcher.addPath(self.watching_path)

    def stop_watching(self):
        """Stop watching the current file."""
        if self.watching_path:
            paths = self.watcher.files()
            if paths:
                self.watcher.removePaths(paths)
            self.watching_path = None
            self.last_known_content = ""

    def update_known_content(self, content: str):
        """
        Update the last known content.

        Call this when the app itself modifies the file, to avoid
        treating our own changes as external edits.
        """
        self.last_known_content = content
        # Set flag to ignore the next file change event
        self._ignore_next_change = True

    def _on_file_changed(self, path: str):
        """Handle file change event from QFileSystemWatcher."""
        if self._ignore_next_change:
            # This change was from our own update
            self._ignore_next_change = False
            return

        # Read new content
        new_content = self._read_file_content()

        # Check if content actually changed
        if new_content != self.last_known_content:
            self.last_known_content = new_content
            self.file_changed_externally.emit(new_content)

            # Re-add the path since QFileSystemWatcher removes it after change on some platforms
            if path not in self.watcher.files():
                self.watcher.addPath(path)

    def _read_file_content(self) -> str:
        """Read the current file content."""
        if not self.watching_path:
            return ""

        try:
            return Path(self.watching_path).read_text(encoding="utf-8")
        except Exception:
            return ""
