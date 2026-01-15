"""Panel for execution configuration options."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QSpinBox, QCheckBox,
    QLineEdit, QPushButton, QHBoxLayout, QGroupBox, QFileDialog
)
from PySide6.QtCore import Signal
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExecutionConfig:
    """Execution configuration settings."""
    max_main_iterations: int
    debug_loop_iterations: int
    auto_push: bool
    working_directory: str


class ConfigPanel(QWidget):
    """
    Configuration options for execution parameters.
    """

    config_changed = Signal()
    working_directory_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Configuration")
        form = QFormLayout(group)

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

        # Auto-push checkbox
        self.auto_push_checkbox = QCheckBox("Auto-push to Git")
        self.auto_push_checkbox.setChecked(False)
        self.auto_push_checkbox.setToolTip(
            "If checked, automatically push after commit. "
            "If unchecked, you'll be asked before pushing."
        )
        self.auto_push_checkbox.stateChanged.connect(self._on_config_changed)
        form.addRow(self.auto_push_checkbox)

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

    def _on_working_dir_changed(self):
        """Handle working directory change."""
        self.working_directory_changed.emit(self.working_dir_edit.text())
        self.config_changed.emit()

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
            auto_push=self.auto_push_checkbox.isChecked(),
            working_directory=self.working_dir_edit.text().strip()
        )

    def set_config(self, config: ExecutionConfig):
        """Set configuration from ExecutionConfig object."""
        self.max_iterations_spin.setValue(config.max_main_iterations)
        self.debug_iterations_spin.setValue(config.debug_loop_iterations)
        self.auto_push_checkbox.setChecked(config.auto_push)
        self.working_dir_edit.setText(config.working_directory)

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
        self.max_iterations_spin.setEnabled(enabled)
        self.debug_iterations_spin.setEnabled(enabled)
        self.auto_push_checkbox.setEnabled(enabled)
        self.browse_button.setEnabled(enabled)
