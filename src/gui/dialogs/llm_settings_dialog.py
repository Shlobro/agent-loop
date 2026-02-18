"""Dialog for selecting LLM providers and models for each workflow stage."""

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ..widgets.llm_selector_panel import LLMSelectorPanel


class LLMSettingsDialog(QDialog):
    """Modal dialog for provider/model selection by stage."""

    def __init__(self, current_config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LLM Settings")
        self.setModal(True)
        self.resize(950, 460)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose provider and model for each workflow stage:"))

        self.selector_panel = LLMSelectorPanel()
        self.selector_panel.set_config(current_config or {})
        layout.addWidget(self.selector_panel)

        buttons = QDialogButtonBox()
        self.save_config_button = QPushButton("Save Config File...")
        self.load_config_button = QPushButton("Load Config File...")
        close_button = QPushButton("Close")

        buttons.addButton(self.save_config_button, QDialogButtonBox.ActionRole)
        buttons.addButton(self.load_config_button, QDialogButtonBox.ActionRole)
        buttons.addButton(close_button, QDialogButtonBox.AcceptRole)

        self.save_config_button.clicked.connect(self._on_save_config_file)
        self.load_config_button.clicked.connect(self._on_load_config_file)
        close_button.clicked.connect(self.accept)
        layout.addWidget(buttons)

    def get_config_dict(self) -> dict:
        """Return selected provider/model values for all stages."""
        return self.selector_panel.get_config_dict()

    def _on_save_config_file(self):
        """Save current stage LLM selections to a reusable JSON file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save LLM Configuration",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if not file_path:
            return

        payload = {
            "llm_config": self.get_config_dict(),
        }
        try:
            Path(file_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            QMessageBox.information(self, "Saved", "LLM configuration file saved.")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save LLM configuration:\n{exc}")

    def _on_load_config_file(self):
        """Load stage LLM selections from a previously saved JSON file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load LLM Configuration",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if not file_path:
            return

        try:
            raw = Path(file_path).read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("Top-level JSON must be an object.")

            config = data.get("llm_config", data)
            if not isinstance(config, dict):
                raise ValueError("Config payload must be a JSON object.")

            self.selector_panel.set_config(config)
            QMessageBox.information(self, "Loaded", "LLM configuration file loaded.")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to load LLM configuration:\n{exc}")
