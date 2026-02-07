"""File manager for tasks.md, recent-changes.md, and review artifacts."""

from pathlib import Path
from typing import Optional
from .exceptions import FileOperationError


class FileManager:
    """
    Manages I/O for tasks.md, recent-changes.md, and review files.
    Provides atomic write operations and error handling.
    """

    TASKS_FILE = "tasks.md"
    RECENT_CHANGES_FILE = "recent-changes.md"
    REVIEW_FILE = "review.md"
    REVIEW_DIR = "review"
    DESCRIPTION_FILE = "product-description.md"
    AGENTS_FILE = "AGENTS.md"
    CLAUDE_FILE = "CLAUDE.md"
    GEMINI_FILE = "GEMINI.md"
    COMMIT_MESSAGE_FILE = ".agentharness/git-commit-message.txt"

    def __init__(self, working_directory: str):
        self.working_dir = Path(working_directory)
        self.tasks_file = self.working_dir / self.TASKS_FILE
        self.recent_changes_file = self.working_dir / self.RECENT_CHANGES_FILE
        self.review_file = self.working_dir / self.REVIEW_FILE
        self.review_dir = self.working_dir / self.REVIEW_DIR

    def set_working_directory(self, working_directory: str):
        """Update the working directory."""
        self.working_dir = Path(working_directory)
        self.tasks_file = self.working_dir / self.TASKS_FILE
        self.recent_changes_file = self.working_dir / self.RECENT_CHANGES_FILE
        self.review_file = self.working_dir / self.REVIEW_FILE
        self.review_dir = self.working_dir / self.REVIEW_DIR

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
            self._ensure_governance_files()
            if not self.tasks_file.exists():
                self.tasks_file.write_text("# Tasks\n\n", encoding="utf-8")

            if not self.recent_changes_file.exists():
                self.recent_changes_file.write_text("# Recent Changes\n\n", encoding="utf-8")

            self.review_dir.mkdir(parents=True, exist_ok=True)
            description_path = self.working_dir / self.DESCRIPTION_FILE
            if not description_path.exists():
                description_path.write_text("", encoding="utf-8")
            commit_message_path = self.working_dir / self.COMMIT_MESSAGE_FILE
            if not commit_message_path.exists():
                commit_message_path.parent.mkdir(parents=True, exist_ok=True)
                commit_message_path.write_text("", encoding="utf-8")
        except OSError as e:
            raise FileOperationError(f"Failed to create files: {e}")

    def _ensure_governance_files(self):
        """Create governance prompt files in the working directory if missing."""
        content = self._default_governance_content()
        governance_files = {
            self.AGENTS_FILE: content,
            self.CLAUDE_FILE: content,
            self.GEMINI_FILE: content,
        }

        for name, file_content in governance_files.items():
            path = self.working_dir / name
            if not path.exists():
                path.write_text(file_content, encoding="utf-8")

    @staticmethod
    def _default_governance_content() -> str:
        """Return the unified default content for governance files (AGENTS.md, CLAUDE.md, GEMINI.md)."""
        return "\n".join([
            "- Always start with reading product-description.md.",
            "- each folder must have a developer-guide.md that must be updated after any change in that folder, if there is a folder with code files and no developer guide then create it.",
            "- the point of the developer guides md files are so that any new developer can understand what is in that folder without having to ever read the code in that folder",
            "- Read the developer guide in the folder you are editing before making changes.",
            "- Update the relevant developer guides and their ancestors when behavior changes.",
            "- There is no reason to mention legacy information in the developer guides the only point is to allow new developers understand the current code without having to read the code.",
            "- Do not create files over 1000 lines; split files when necessary.",
            "- Keep folders under 10 code files; `.md` files do not count.",
            "- Keep .md developer guides under 500 lines long. if there is a developer guide that is longer then compact it while making sure it still gives all the information needed to understand all code files in that folder.",
        ]) + "\n"

    @staticmethod
    def _default_agents_content() -> str:
        """Return default AGENTS.md content for new workspaces."""
        return FileManager._default_governance_content()

    @staticmethod
    def _default_claude_content() -> str:
        """Return default CLAUDE.md content for new workspaces."""
        return FileManager._default_governance_content()

    @staticmethod
    def _default_gemini_content() -> str:
        """Return default GEMINI.md content for new workspaces."""
        return FileManager._default_governance_content()

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

    def ensure_review_files_exist(self, review_filenames: list[str]):
        """Create review directory and any missing review files."""
        try:
            self.review_dir.mkdir(parents=True, exist_ok=True)
            for filename in review_filenames:
                filepath = self.working_dir / filename
                filepath.parent.mkdir(parents=True, exist_ok=True)
                if not filepath.exists():
                    filepath.write_text("", encoding="utf-8")
        except OSError as e:
            raise FileOperationError(f"Failed to create review files: {e}")

    def read_review_file(self, filename: str) -> str:
        """Read one review file from the working directory."""
        filepath = self.working_dir / filename
        try:
            if filepath.exists():
                return filepath.read_text(encoding="utf-8")
            return ""
        except OSError as e:
            raise FileOperationError(f"Failed to read {filename}: {e}")

    def truncate_review_file(self, filename: str):
        """Clear one review file after fixer has processed it."""
        filepath = self.working_dir / filename
        self._atomic_write(filepath, "")

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
