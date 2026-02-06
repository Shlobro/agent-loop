"""File manager for tasks.md, recent-changes.md, and review.md."""

import os
import time
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
    DESCRIPTION_FILE = "product-description.md"
    AGENTS_FILE = "AGENTS.md"
    CLAUDE_FILE = "CLAUDE.md"
    GEMINI_FILE = "GEMINI.md"
    DEFAULT_MAX_FILES_PER_DIRECTORY = 10
    DEFAULT_MAX_LINES_PER_FILE = 1000
    DEFAULT_MAX_DEV_GUIDE_LINES = 500
    DEFAULT_IGNORE_DIRS = {
        ".git",
        ".venv",
        "node_modules",
        ".idea",
        ".claude",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        "dist",
        "build",
        "out",
    }
    DEFAULT_CODE_EXTENSIONS = {
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".java",
        ".kt",
        ".go",
        ".rs",
        ".c",
        ".h",
        ".cpp",
        ".hpp",
        ".cs",
        ".swift",
        ".php",
        ".rb",
        ".sh",
        ".ps1",
        ".psm1",
        ".html",
        ".css",
        ".scss",
    }

    def __init__(self, working_directory: str):
        self.working_dir = Path(working_directory)
        self.tasks_file = self.working_dir / self.TASKS_FILE
        self.recent_changes_file = self.working_dir / self.RECENT_CHANGES_FILE
        self.review_file = self.working_dir / self.REVIEW_FILE
        self._last_scan_time = None
        self._last_scan_report = None
        self._last_scan_params = None

    def set_working_directory(self, working_directory: str):
        """Update the working directory."""
        self.working_dir = Path(working_directory)
        self.tasks_file = self.working_dir / self.TASKS_FILE
        self.recent_changes_file = self.working_dir / self.RECENT_CHANGES_FILE
        self.review_file = self.working_dir / self.REVIEW_FILE
        self._clear_scan_cache()

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

            if not self.review_file.exists():
                self.review_file.write_text("", encoding="utf-8")
            description_path = self.working_dir / self.DESCRIPTION_FILE
            if not description_path.exists():
                description_path.write_text("", encoding="utf-8")
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

    def scan_workspace_rules(
        self,
        max_files_per_directory: int = DEFAULT_MAX_FILES_PER_DIRECTORY,
        max_lines_per_file: int = DEFAULT_MAX_LINES_PER_FILE,
        code_extensions: Optional[set] = None,
        ignore_dirs: Optional[set] = None
    ) -> dict:
        """Scan the working directory for workspace rule compliance."""
        code_extensions = code_extensions or self.DEFAULT_CODE_EXTENSIONS
        ignore_dirs = ignore_dirs or self.DEFAULT_IGNORE_DIRS

        missing_md_dirs = []
        multi_md_dirs = []
        overfull_dirs = []
        oversized_files = []

        if not self.is_valid_directory():
            return {
                "missing_md_dirs": missing_md_dirs,
                "multi_md_dirs": [],
                "overfull_dirs": overfull_dirs,
                "oversized_files": oversized_files,
                "error": "Working directory is missing or inaccessible.",
            }

        for dirpath, dirnames, filenames in os.walk(self.working_dir):
            dirnames[:] = [d for d in dirnames if d not in ignore_dirs]
            path = Path(dirpath)

            is_root = path == self.working_dir
            md_count = sum(1 for name in filenames if name.lower().endswith(".md"))
            if md_count == 0:
                missing_md_dirs.append(self._relative_path(path))
            elif md_count > 1 and not is_root:
                multi_md_dirs.append({
                    "path": self._relative_path(path),
                    "md_count": md_count,
                })

            code_file_count = sum(
                1 for name in filenames
                if self._is_code_file(path / name, code_extensions)
            )
            if code_file_count > max_files_per_directory:
                overfull_dirs.append({
                    "path": self._relative_path(path),
                    "file_count": code_file_count,
                })

            for name in filenames:
                file_path = path / name
                if not self._is_code_file(file_path, code_extensions):
                    continue
                line_count = self._count_file_lines(file_path)
                if line_count > max_lines_per_file:
                    oversized_files.append({
                        "path": self._relative_path(file_path),
                        "line_count": line_count,
                    })

        return {
            "missing_md_dirs": missing_md_dirs,
            "multi_md_dirs": multi_md_dirs,
            "overfull_dirs": overfull_dirs,
            "oversized_files": oversized_files,
            "error": None,
        }

    def get_workspace_rule_report(
        self,
        max_items_per_section: int = 10,
        max_files_per_directory: int = DEFAULT_MAX_FILES_PER_DIRECTORY,
        max_lines_per_file: int = DEFAULT_MAX_LINES_PER_FILE,
        code_extensions: Optional[set] = None,
        ignore_dirs: Optional[set] = None,
        use_cache: bool = True,
        cache_ttl_seconds: int = 5
    ) -> str:
        """Return a human-readable workspace rule report."""
        scan_params = (
            str(self.working_dir),
            max_items_per_section,
            max_files_per_directory,
            max_lines_per_file,
            tuple(sorted((code_extensions or self.DEFAULT_CODE_EXTENSIONS))),
            tuple(sorted((ignore_dirs or self.DEFAULT_IGNORE_DIRS))),
        )
        if use_cache and self._last_scan_report and self._last_scan_params == scan_params:
            if time.time() - self._last_scan_time < cache_ttl_seconds:
                return self._last_scan_report

        report = self.scan_workspace_rules(
            max_files_per_directory=max_files_per_directory,
            max_lines_per_file=max_lines_per_file,
            code_extensions=code_extensions,
            ignore_dirs=ignore_dirs
        )
        formatted = self.format_workspace_rule_report(report, max_items_per_section)
        self._last_scan_report = formatted
        self._last_scan_time = time.time()
        self._last_scan_params = scan_params
        return formatted

    @staticmethod
    def format_workspace_rule_report(report: dict, max_items_per_section: int = 10) -> str:
        """Format a workspace rule report for prompt usage."""
        sections = []

        error = report.get("error")
        if error:
            return f"Workspace compliance scan failed: {error}"

        missing_md_dirs = report.get("missing_md_dirs", [])
        if missing_md_dirs:
            section = FileManager._format_section(
                "Missing developer guide .md files (one per folder):",
                missing_md_dirs,
                max_items_per_section
            )
            sections.append(section)

        multi_md_dirs = report.get("multi_md_dirs", [])
        if multi_md_dirs:
            entries = [
                f"{item['path']} ({item['md_count']} .md files)"
                for item in multi_md_dirs
            ]
            section = FileManager._format_section(
                "Folders with multiple developer guide .md files:",
                entries,
                max_items_per_section
            )
            sections.append(section)

        overfull_dirs = report.get("overfull_dirs", [])
        if overfull_dirs:
            entries = [
                f"{item['path']} ({item['file_count']} code files)"
                for item in overfull_dirs
            ]
            section = FileManager._format_section(
                "Folders with more than 10 code files:",
                entries,
                max_items_per_section
            )
            sections.append(section)

        oversized_files = report.get("oversized_files", [])
        if oversized_files:
            entries = [
                f"{item['path']} ({item['line_count']} lines)"
                for item in oversized_files
            ]
            section = FileManager._format_section(
                "Code files over 1000 lines:",
                entries,
                max_items_per_section
            )
            sections.append(section)

        if not sections:
            return "No compliance issues detected."
        return "\n\n".join(sections)

    @staticmethod
    def _format_section(title: str, entries: list, max_items: int) -> str:
        """Format a report section with optional truncation."""
        lines = [title]
        display = entries[:max_items]
        lines.extend(f"- {entry}" for entry in display)
        if len(entries) > max_items:
            lines.append(f"- ... and {len(entries) - max_items} more")
        return "\n".join(lines)

    def _relative_path(self, path: Path) -> str:
        """Return a workspace-relative path for display."""
        try:
            rel_path = path.relative_to(self.working_dir)
        except ValueError:
            return str(path)
        if rel_path == Path("."):
            return "."
        return str(rel_path)

    @staticmethod
    def _is_code_file(path: Path, code_extensions: set) -> bool:
        """Return True if the file should count toward code line limits."""
        return path.is_file() and path.suffix.lower() in code_extensions

    @staticmethod
    def _count_file_lines(path: Path) -> int:
        """Count lines in a text file, ignoring encoding errors."""
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                return sum(1 for _ in handle)
        except OSError:
            return 0

    def _clear_scan_cache(self):
        """Clear cached workspace compliance scan results."""
        self._last_scan_time = None
        self._last_scan_report = None
        self._last_scan_params = None
