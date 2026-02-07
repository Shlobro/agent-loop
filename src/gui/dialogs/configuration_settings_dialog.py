"""Dialog for editing execution and project configuration settings."""

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

from ..widgets.config_panel import ConfigPanel, ExecutionConfig


class ConfigurationSettingsDialog(QDialog):
    """Modal dialog for execution settings and working-directory configuration."""

    def __init__(self, current_config: ExecutionConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration Settings")
        self.setModal(True)
        self.resize(700, 420)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Configure workflow execution and project directory settings:"))

        self.config_panel = ConfigPanel()
        self.config_panel.set_config(current_config)
        layout.addWidget(self.config_panel)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_config(self) -> ExecutionConfig:
        """Return the selected execution config values."""
        return self.config_panel.get_config()
