"""File manager for tasks.md, recent-changes.md, and review.md."""

from pathlib import Path
from typing import Optional
from .exceptions import FileOperationError


class FileManager:
    """
    Manages I/O for tasks.md, recent-changes.md, and review.md files.
    Provides atomic write operations and error handling.
    """

    TASKS_FILE = "tasks.md"
    RECENT_CHANGES_FILE = "recent-changes.md"
    REVIEW_FILE = "review.md"

    def __init__(self, working_directory: str):
        self.working_dir = Path(working_directory)
        self.tasks_file = self.working_dir / self.TASKS_FILE
        self.recent_changes_file = self.working_dir / self.RECENT_CHANGES_FILE
        self.review_file = self.working_dir / self.REVIEW_FILE

    def set_working_directory(self, working_directory: str):
        """Update the working directory."""
        self.working_dir = Path(working_directory)
        self.tasks_file = self.working_dir / self.TASKS_FILE
        self.recent_changes_file = self.working_dir / self.RECENT_CHANGES_FILE
        self.review_file = self.working_dir / self.REVIEW_FILE

    def ensure_directory_exists(self):
        """Create working directory if it doesn't exist."""
        try:
            self.working_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise FileOperationError(f"Failed to create directory: {e}")

    def ensure_files_exist(self):
        """Create tracking files if they don't exist."""
        self.ensure_directory_exists()

        try:
            if not self.tasks_file.exists():
                self.tasks_file.write_text("# Tasks\n\n", encoding="utf-8")

            if not self.recent_changes_file.exists():
                self.recent_changes_file.write_text("# Recent Changes\n\n", encoding="utf-8")

            if not self.review_file.exists():
                self.review_file.write_text("", encoding="utf-8")
        except OSError as e:
            raise FileOperationError(f"Failed to create files: {e}")

    def read_tasks(self) -> str:
        """Read tasks.md content."""
        try:
            if self.tasks_file.exists():
                return self.tasks_file.read_text(encoding="utf-8")
            return ""
        except OSError as e:
            raise FileOperationError(f"Failed to read tasks.md: {e}")

    def write_tasks(self, content: str):
        """Write tasks.md content atomically."""
        self._atomic_write(self.tasks_file, content)

    def read_recent_changes(self) -> str:
        """Read recent-changes.md content."""
        try:
            if self.recent_changes_file.exists():
                return self.recent_changes_file.read_text(encoding="utf-8")
            return ""
        except OSError as e:
            raise FileOperationError(f"Failed to read recent-changes.md: {e}")

    def write_recent_changes(self, content: str):
        """Write recent-changes.md content."""
        self._atomic_write(self.recent_changes_file, content)

    def append_recent_changes(self, content: str):
        """Append to recent-changes.md."""
        existing = self.read_recent_changes()
        self.write_recent_changes(existing + "\n" + content)

    def read_review(self) -> str:
        """Read review.md content."""
        try:
            if self.review_file.exists():
                return self.review_file.read_text(encoding="utf-8")
            return ""
        except OSError as e:
            raise FileOperationError(f"Failed to read review.md: {e}")

    def write_review(self, content: str):
        """Write review.md content."""
        self._atomic_write(self.review_file, content)

    def truncate_review(self):
        """Clear review.md after fixer has processed it."""
        self._atomic_write(self.review_file, "")

    def _atomic_write(self, filepath: Path, content: str):
        """Write file atomically using temp file and rename."""
        temp_path = filepath.with_suffix(".tmp")
        try:
            # Ensure parent directory exists
            filepath.parent.mkdir(parents=True, exist_ok=True)

            temp_path.write_text(content, encoding="utf-8")
            temp_path.replace(filepath)  # Atomic on POSIX, near-atomic on Windows
        except OSError as e:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            raise FileOperationError(f"Failed to write {filepath.name}: {e}")

    def file_exists(self, filename: str) -> bool:
        """Check if a file exists in the working directory."""
        return (self.working_dir / filename).exists()

    def read_file(self, filename: str) -> Optional[str]:
        """Read any file from the working directory."""
        filepath = self.working_dir / filename
        try:
            if filepath.exists():
                return filepath.read_text(encoding="utf-8")
            return None
        except OSError as e:
            raise FileOperationError(f"Failed to read {filename}: {e}")

    def write_file(self, filename: str, content: str):
        """Write any file to the working directory."""
        filepath = self.working_dir / filename
        self._atomic_write(filepath, content)

    def get_working_directory(self) -> str:
        """Return the current working directory path."""
        return str(self.working_dir)

    def is_valid_directory(self) -> bool:
        """Check if working directory exists and is accessible."""
        return self.working_dir.exists() and self.working_dir.is_dir()
