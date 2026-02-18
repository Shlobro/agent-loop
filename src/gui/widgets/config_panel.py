"""Panel for execution configuration options."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLabel,
    QLineEdit, QPushButton, QHBoxLayout, QGroupBox, QFileDialog,
    QSpinBox, QMessageBox
)
from PySide6.QtCore import Signal
from dataclasses import dataclass, field
from pathlib import Path
import subprocess
from typing import List, Optional

from ...llm.prompt_templates import PromptTemplates, ReviewType
from ..dialogs.review_settings_dialog import ReviewSettingsDialog


@dataclass
class ExecutionConfig:
    """Execution configuration settings."""
    max_main_iterations: int
    debug_loop_iterations: int
    working_directory: str
    git_remote: str = ""
    git_mode: str = "local"
    max_questions: int = 5
    review_types: List[str] = field(
        default_factory=lambda: [ReviewType.GENERAL.value]
    )
    run_unit_test_prep: bool = True
    tasks_per_iteration: int = 1


class ConfigPanel(QWidget):
    """
    Configuration options for execution parameters.
    """

    config_changed = Signal()
    working_directory_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._git_mode = "local"
        self._controls_enabled = True
        self._all_review_types = [r.value for r in PromptTemplates.get_all_review_types()]
        self._selected_review_types = [ReviewType.GENERAL.value]
        self._run_unit_test_prep = True
        self._git_install_notice_shown = False
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Configuration")
        form = QFormLayout(group)

        # Number of clarifying questions to generate per batch
        self.max_questions_spin = QSpinBox()
        self.max_questions_spin.setRange(0, 100)
        self.max_questions_spin.setValue(5)
        self.max_questions_spin.setToolTip(
            "Number of clarifying questions to generate per batch. "
            "Set to 0 to skip clarifying questions."
        )
        self.max_questions_spin.valueChanged.connect(self._on_config_changed)
        form.addRow("Number of Questions:", self.max_questions_spin)

        # Max iterations for main loop
        self.max_iterations_spin = QSpinBox()
        self.max_iterations_spin.setRange(1, 1000)
        self.max_iterations_spin.setValue(10)
        self.max_iterations_spin.setToolTip("Maximum iterations for the main execution loop")
        self.max_iterations_spin.valueChanged.connect(self._on_config_changed)
        form.addRow("Max Main Iterations:", self.max_iterations_spin)

        # Tasks per iteration
        self.tasks_per_iteration_spin = QSpinBox()
        self.tasks_per_iteration_spin.setRange(1, 20)
        self.tasks_per_iteration_spin.setValue(1)
        self.tasks_per_iteration_spin.setToolTip(
            "Number of tasks the LLM should tackle per iteration. "
            "Increase for stronger models that can handle multiple tasks at once."
        )
        self.tasks_per_iteration_spin.valueChanged.connect(self._on_config_changed)
        form.addRow("Tasks Per Iteration:", self.tasks_per_iteration_spin)

        # Debug loop iterations
        self.debug_iterations_spin = QSpinBox()
        self.debug_iterations_spin.setRange(0, 20)
        self.debug_iterations_spin.setValue(1)
        self.debug_iterations_spin.setToolTip("Number of debug/review loop iterations (0 to skip)")
        self.debug_iterations_spin.valueChanged.connect(self._on_config_changed)
        form.addRow("Debug Loop Iterations:", self.debug_iterations_spin)

        # Git remote URL
        self.git_remote_label = QLabel("Git Remote URL:")
        self.git_remote_edit = QLineEdit()
        self.git_remote_edit.setPlaceholderText("e.g., https://github.com/user/repo.git")
        self.git_remote_edit.setToolTip(
            "Git remote URL (GitHub, GitLab, etc.). "
            "Will be set as 'origin' remote before pushing."
        )
        self.git_remote_edit.textChanged.connect(self._on_git_remote_changed)
        self.git_remote_edit.textChanged.connect(self._on_config_changed)
        form.addRow(self.git_remote_label, self.git_remote_edit)
        self.git_remote_label.setVisible(False)
        self.git_remote_edit.setVisible(False)

        # Working directory
        dir_layout = QHBoxLayout()
        self.working_dir_edit = QLineEdit()
        self.working_dir_edit.setPlaceholderText("Select project working directory...")
        self.working_dir_edit.setReadOnly(True)
        self.working_dir_edit.textChanged.connect(self._on_working_dir_changed)
        dir_layout.addWidget(self.working_dir_edit)

        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self._on_browse_clicked)
        dir_layout.addWidget(self.browse_button)

        form.addRow("Working Directory:", dir_layout)

        layout.addWidget(group)

    def _on_config_changed(self):
        """Emit signal when configuration changes."""
        self.config_changed.emit()

    def open_review_settings(self):
        """Open dialog for selecting review types."""
        dialog = ReviewSettingsDialog(
            self._selected_review_types,
            self._run_unit_test_prep,
            self
        )
        if dialog.exec():
            self._selected_review_types = dialog.get_selected_review_types()
            self._run_unit_test_prep = dialog.get_run_unit_test_prep()
            self._on_config_changed()

    def _on_working_dir_changed(self):
        """Handle working directory change."""
        path = self.working_dir_edit.text()
        if path and Path(path).exists() and Path(path).is_dir():
            self.ensure_git_ready(path, self.git_remote_edit.text().strip())
        self.working_directory_changed.emit(path)
        self.config_changed.emit()

    def _on_git_remote_changed(self):
        """Apply remote configuration when git remote text changes."""
        directory = self.get_working_directory()
        remote = self.git_remote_edit.text().strip()
        if not directory or not remote:
            return
        if not Path(directory).exists() or not Path(directory).is_dir():
            return
        self.ensure_git_ready(directory, remote)

    def ensure_git_ready(self, directory: str = "", remote: Optional[str] = None) -> bool:
        """Ensure git repository and remote setup for a working directory."""
        target_dir = (directory or self.get_working_directory() or "").strip()
        if not target_dir:
            return False
        path_obj = Path(target_dir)
        if not path_obj.exists() or not path_obj.is_dir():
            return False
        if not self._ensure_git_repository(target_dir):
            return False
        remote_url = self.git_remote_edit.text().strip() if remote is None else remote.strip()
        if remote_url:
            self._setup_git_remote(target_dir, remote_url)
        return True

    def _show_git_install_notice(self):
        """Show a one-time notice that git is required."""
        if self._git_install_notice_shown:
            return
        self._git_install_notice_shown = True
        QMessageBox.critical(
            self,
            "Git Required",
            "Git is required but is not installed or not available in PATH.\n"
            "Please install Git and restart the application."
        )

    def _run_git_command(self, directory: str, args: List[str], timeout: int = 10):
        """Run a git command in the given directory."""
        return subprocess.run(
            ["git", *args],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )

    def _ensure_git_repository(self, directory: str) -> bool:
        """Ensure directory is a git repository; initialize it if needed."""
        try:
            repo_check = self._run_git_command(directory, ["rev-parse", "--is-inside-work-tree"])
        except OSError:
            self._show_git_install_notice()
            return False
        except subprocess.SubprocessError:
            repo_check = None

        if repo_check and repo_check.returncode == 0 and repo_check.stdout.strip() == "true":
            return True

        try:
            init_result = self._run_git_command(directory, ["init"])
        except OSError:
            self._show_git_install_notice()
            return False
        except subprocess.SubprocessError as exc:
            QMessageBox.warning(
                self,
                "Git Initialization Failed",
                "Failed to run `git init`.\n"
                "Please install Git and ensure it is available in PATH.\n\n"
                f"Details: {exc}"
            )
            return False

        if init_result.returncode != 0:
            details = init_result.stderr.strip() or init_result.stdout.strip() or "Unknown error."
            QMessageBox.warning(
                self,
                "Git Initialization Failed",
                "Failed to initialize a git repository with `git init`.\n"
                "Please install Git and ensure it is available in PATH.\n\n"
                f"Details: {details}"
            )
            return False

        return True

    def _setup_git_remote(self, directory: str, remote: str):
        """Ensure origin points at the configured remote URL."""
        if not remote:
            return
        try:
            existing = self._run_git_command(directory, ["remote", "get-url", "origin"])
        except OSError:
            self._show_git_install_notice()
            return
        except subprocess.SubprocessError:
            return

        command = None
        if existing.returncode == 0:
            current_remote = existing.stdout.strip()
            if current_remote == remote:
                return
            command = ["remote", "set-url", "origin", remote]
        else:
            command = ["remote", "add", "origin", remote]

        try:
            update = self._run_git_command(directory, command)
        except OSError:
            self._show_git_install_notice()
            return
        except subprocess.SubprocessError as exc:
            QMessageBox.warning(
                self,
                "Git Remote Setup Failed",
                f"Failed to configure git remote origin.\n\nDetails: {exc}"
            )
            return

        if update.returncode != 0:
            details = update.stderr.strip() or update.stdout.strip() or "Unknown error."
            QMessageBox.warning(
                self,
                "Git Remote Setup Failed",
                "Failed to configure git remote origin.\n\n"
                f"Details: {details}"
            )

    def _detect_git_remote(self, directory: str) -> str:
        """Detect the git remote URL for origin in the given directory."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.SubprocessError, OSError):
            pass
        return ""

    def _on_browse_clicked(self):
        """Open directory browser dialog."""
        current = self.working_dir_edit.text()
        start_dir = current if current and Path(current).exists() else str(Path.home())

        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Working Directory",
            start_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if directory:
            self.working_dir_edit.setText(directory)

    def get_config(self) -> ExecutionConfig:
        """Get current configuration."""
        return ExecutionConfig(
            max_main_iterations=self.max_iterations_spin.value(),
            debug_loop_iterations=self.debug_iterations_spin.value(),
            working_directory=self.working_dir_edit.text().strip(),
            git_remote=self.git_remote_edit.text().strip(),
            git_mode=self._git_mode,
            max_questions=self.max_questions_spin.value(),
            review_types=self.get_review_types(),
            run_unit_test_prep=self.get_run_unit_test_prep(),
            tasks_per_iteration=self.tasks_per_iteration_spin.value()
        )

    def set_config(self, config: ExecutionConfig):
        """Set configuration from ExecutionConfig object."""
        self.max_questions_spin.setValue(config.max_questions)
        self.max_iterations_spin.setValue(config.max_main_iterations)
        self.debug_iterations_spin.setValue(config.debug_loop_iterations)
        self.working_dir_edit.setText(config.working_directory)
        self.git_remote_edit.setText(config.git_remote or "")
        self.set_git_mode(config.git_mode)
        selected = config.review_types if config.review_types is not None else self._all_review_types
        self._selected_review_types = [review for review in self._all_review_types if review in set(selected)]
        self._run_unit_test_prep = bool(config.run_unit_test_prep)
        self.tasks_per_iteration_spin.setValue(config.tasks_per_iteration)

    def get_review_types(self) -> List[str]:
        """Get the selected review types."""
        return [
            review_type for review_type in self._selected_review_types
        ]

    def get_run_unit_test_prep(self) -> bool:
        """Return whether pre-review unit test update phase is enabled."""
        return self._run_unit_test_prep

    def set_working_directory(self, path: str):
        """Set the working directory."""
        self.working_dir_edit.setText(path)

    def get_working_directory(self) -> str:
        """Get the working directory."""
        return self.working_dir_edit.text().strip()

    def has_valid_working_directory(self) -> bool:
        """Check if a valid working directory is set."""
        path = self.get_working_directory()
        return bool(path) and Path(path).exists() and Path(path).is_dir()

    def set_enabled(self, enabled: bool):
        """Enable or disable controls that must remain static during a run."""
        self._controls_enabled = enabled
        # These remain editable so users can adjust upcoming phases/iterations live.
        self.max_questions_spin.setEnabled(True)
        self.max_iterations_spin.setEnabled(True)
        self.debug_iterations_spin.setEnabled(True)
        self.tasks_per_iteration_spin.setEnabled(True)
        self.browse_button.setEnabled(enabled)

    def set_git_mode(self, mode: str):
        """Update the git mode and refresh related controls."""
        self._git_mode = mode
        self._on_config_changed()

    def set_git_remote(self, remote: str):
        """Store the git remote URL without showing it in the UI."""
        self.git_remote_edit.setText(remote)

    def get_git_remote(self) -> str:
        """Return the current git remote URL."""
        return self.git_remote_edit.text().strip()

    def get_git_mode(self) -> str:
        """Return the current git mode."""
        return self._git_mode
