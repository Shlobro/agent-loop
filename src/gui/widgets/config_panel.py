"""Panel for execution configuration options."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QSpinBox, QCheckBox, QLabel,
    QLineEdit, QPushButton, QHBoxLayout, QGroupBox, QFileDialog
)
from PySide6.QtCore import Signal
from dataclasses import dataclass, field
from pathlib import Path
import subprocess
from typing import List, Dict

from ...llm.prompt_templates import PromptTemplates


@dataclass
class ExecutionConfig:
    """Execution configuration settings."""
    max_main_iterations: int
    debug_loop_iterations: int
    working_directory: str
    git_remote: str = ""
    git_mode: str = "local"
    max_questions: int = 20
    review_types: List[str] = field(
        default_factory=lambda: [r.value for r in PromptTemplates.get_all_review_types()]
    )


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
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Configuration")
        form = QFormLayout(group)

        # Number of clarifying questions to generate per batch
        self.max_questions_spin = QSpinBox()
        self.max_questions_spin.setRange(0, 100)
        self.max_questions_spin.setValue(20)
        self.max_questions_spin.setToolTip(
            "Number of clarifying questions to generate per batch. "
            "Set to 0 to skip clarifying questions."
        )
        self.max_questions_spin.valueChanged.connect(self._on_config_changed)
        form.addRow("Number of Questions:", self.max_questions_spin)

        # Max iterations for main loop
        self.max_iterations_spin = QSpinBox()
        self.max_iterations_spin.setRange(1, 1000)
        self.max_iterations_spin.setValue(50)
        self.max_iterations_spin.setToolTip("Maximum iterations for the main execution loop")
        self.max_iterations_spin.valueChanged.connect(self._on_config_changed)
        form.addRow("Max Main Iterations:", self.max_iterations_spin)

        # Debug loop iterations
        self.debug_iterations_spin = QSpinBox()
        self.debug_iterations_spin.setRange(0, 20)
        self.debug_iterations_spin.setValue(5)
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

        self.review_checkboxes: Dict[str, QCheckBox] = {}
        reviews_group = QGroupBox("Review Types")
        reviews_layout = QVBoxLayout(reviews_group)
        for review_type in PromptTemplates.get_all_review_types():
            label = PromptTemplates.get_review_display_name(review_type)
            checkbox = QCheckBox(label)
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(self._on_config_changed)
            self.review_checkboxes[review_type.value] = checkbox
            reviews_layout.addWidget(checkbox)

        layout.addWidget(group)
        layout.addWidget(reviews_group)

    def _on_config_changed(self):
        """Emit signal when configuration changes."""
        self.config_changed.emit()

    def _on_working_dir_changed(self):
        """Handle working directory change."""
        path = self.working_dir_edit.text()
        self.working_directory_changed.emit(path)
        self.config_changed.emit()

    def _detect_git_remote(self, directory: str) -> str:
        """Detect the git remote URL for origin in the given directory."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=5
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
            review_types=self.get_review_types()
        )

    def set_config(self, config: ExecutionConfig):
        """Set configuration from ExecutionConfig object."""
        self.max_questions_spin.setValue(config.max_questions)
        self.max_iterations_spin.setValue(config.max_main_iterations)
        self.debug_iterations_spin.setValue(config.debug_loop_iterations)
        self.working_dir_edit.setText(config.working_directory)
        self.git_remote_edit.setText(config.git_remote or "")
        self.set_git_mode(config.git_mode)
        selected = set(config.review_types or [])
        for review_type, checkbox in self.review_checkboxes.items():
            checkbox.setChecked(review_type in selected)

    def get_review_types(self) -> List[str]:
        """Get the selected review types."""
        return [
            review_type
            for review_type, checkbox in self.review_checkboxes.items()
            if checkbox.isChecked()
        ]

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
        """Enable or disable all controls."""
        self._controls_enabled = enabled
        self.max_questions_spin.setEnabled(enabled)
        self.max_iterations_spin.setEnabled(enabled)
        self.debug_iterations_spin.setEnabled(enabled)
        self.browse_button.setEnabled(enabled)
        for checkbox in self.review_checkboxes.values():
            checkbox.setEnabled(enabled)

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
