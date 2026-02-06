"""Dialog for configuring debug breakpoints and terminal visibility."""

from typing import Dict

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
)

from ...core.debug_settings import DEBUG_STAGE_LABELS, normalize_debug_breakpoints


class DebugSettingsDialog(QDialog):
    """Modal dialog for workflow debug controls."""

    def __init__(
        self,
        debug_enabled: bool,
        breakpoints: Dict[str, Dict[str, bool]],
        show_terminals: bool,
        parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Debug Settings")
        self.setModal(True)
        self.resize(560, 460)

        normalized = normalize_debug_breakpoints(breakpoints)
        self.stage_checkboxes: Dict[str, Dict[str, QCheckBox]] = {}

        layout = QVBoxLayout(self)

        self.debug_enabled_checkbox = QCheckBox("Enable debug step mode")
        self.debug_enabled_checkbox.setChecked(debug_enabled)
        layout.addWidget(self.debug_enabled_checkbox)

        self.show_terminals_checkbox = QCheckBox("Show terminal window for each LLM call")
        self.show_terminals_checkbox.setChecked(show_terminals)
        layout.addWidget(self.show_terminals_checkbox)

        layout.addWidget(QLabel("Pause points by stage:"))
        layout.addWidget(QLabel("Check Before and/or After to require clicking Next Step."))

        stage_group = QGroupBox("Stage Breakpoints")
        stage_layout = QGridLayout(stage_group)
        stage_layout.addWidget(QLabel("Stage"), 0, 0)
        stage_layout.addWidget(QLabel("Before"), 0, 1)
        stage_layout.addWidget(QLabel("After"), 0, 2)

        for row, (stage, label) in enumerate(DEBUG_STAGE_LABELS.items(), start=1):
            before_checkbox = QCheckBox()
            after_checkbox = QCheckBox()
            before_checkbox.setChecked(normalized[stage]["before"])
            after_checkbox.setChecked(normalized[stage]["after"])
            stage_layout.addWidget(QLabel(label), row, 0)
            stage_layout.addWidget(before_checkbox, row, 1)
            stage_layout.addWidget(after_checkbox, row, 2)
            self.stage_checkboxes[stage] = {
                "before": before_checkbox,
                "after": after_checkbox,
            }

        layout.addWidget(stage_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_debug_enabled(self) -> bool:
        """Return whether debug step mode is enabled."""
        return self.debug_enabled_checkbox.isChecked()

    def get_show_terminals(self) -> bool:
        """Return whether per-call terminal windows should be shown."""
        return self.show_terminals_checkbox.isChecked()

    def get_breakpoints(self) -> Dict[str, Dict[str, bool]]:
        """Return the selected before/after breakpoints per stage."""
        return {
            stage: {
                "before": controls["before"].isChecked(),
                "after": controls["after"].isChecked(),
            }
            for stage, controls in self.stage_checkboxes.items()
        }

