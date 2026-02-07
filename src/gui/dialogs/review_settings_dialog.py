"""Dialog for selecting which review types should run."""

from typing import Dict, List

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

from ...llm.prompt_templates import PromptTemplates


class ReviewSettingsDialog(QDialog):
    """Modal dialog for review type selection."""

    def __init__(self, selected_review_types: List[str], run_unit_test_prep: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Review Settings")
        self.setModal(True)
        self.resize(360, 400)

        selected = set(selected_review_types or [])
        self.review_checkboxes: Dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose which reviewers should run:"))

        self.unit_test_prep_checkbox = QCheckBox("Run pre-review unit test update phase")
        self.unit_test_prep_checkbox.setChecked(run_unit_test_prep)
        layout.addWidget(self.unit_test_prep_checkbox)

        for review_type in PromptTemplates.get_all_review_types():
            value = review_type.value
            label = PromptTemplates.get_review_display_name(review_type)
            checkbox = QCheckBox(label)
            checkbox.setChecked(value in selected)
            self.review_checkboxes[value] = checkbox
            layout.addWidget(checkbox)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_selected_review_types(self) -> List[str]:
        """Return selected review type values."""
        return [
            review_type
            for review_type, checkbox in self.review_checkboxes.items()
            if checkbox.isChecked()
        ]

    def get_run_unit_test_prep(self) -> bool:
        """Return whether pre-review unit test update phase is enabled."""
        return self.unit_test_prep_checkbox.isChecked()
