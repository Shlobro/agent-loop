"""Dialog for selecting which review types should run."""

from typing import Dict, List

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
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

        prep_group = QGroupBox("Pre-Review Preparation")
        prep_layout = QVBoxLayout(prep_group)
        prep_note = QLabel(
            "Runs once before the review loop starts (not a review-type cycle)."
        )
        prep_note.setWordWrap(True)
        prep_note.setProperty("role", "muted")
        prep_layout.addWidget(prep_note)

        self.unit_test_prep_checkbox = QCheckBox("Run unit test prep before review loop")
        self.unit_test_prep_checkbox.setChecked(run_unit_test_prep)
        prep_layout.addWidget(self.unit_test_prep_checkbox)
        layout.addWidget(prep_group)

        review_group = QGroupBox("Review Loop Types")
        review_layout = QVBoxLayout(review_group)
        review_note = QLabel("Choose which reviewers run inside each review iteration.")
        review_note.setWordWrap(True)
        review_note.setProperty("role", "muted")
        review_layout.addWidget(review_note)

        for review_type in PromptTemplates.get_all_review_types():
            value = review_type.value
            label = PromptTemplates.get_review_display_name(review_type)
            checkbox = QCheckBox(label)
            checkbox.setChecked(value in selected)
            self.review_checkboxes[value] = checkbox
            review_layout.addWidget(checkbox)
        layout.addWidget(review_group)

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
