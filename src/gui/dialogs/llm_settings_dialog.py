"""Dialog for selecting LLM providers and models for each workflow stage."""

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
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

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_config_dict(self) -> dict:
        """Return selected provider/model values for all stages."""
        return self.selector_panel.get_config_dict()
