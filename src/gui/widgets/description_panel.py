"""Panel for user project description input."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit, QGroupBox
)
from PySide6.QtCore import Signal


class DescriptionPanel(QWidget):
    """
    Panel for user to enter project description.
    Emits signal when description changes.
    """

    description_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Group box for visual grouping
        group = QGroupBox("Project Description")
        group_layout = QVBoxLayout(group)

        # Instructions label
        instructions = QLabel(
            "Describe what you want to build. Be specific about features, "
            "requirements, and any technical constraints."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: gray; font-size: 11px;")
        group_layout.addWidget(instructions)

        # Text input
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText(
            "Example: I want to build a REST API for a library catalog system. "
            "It should have endpoints for managing books (CRUD operations), "
            "authors, and borrowing records. Users should be able to search "
            "books by title, author, or ISBN. The API should use JWT for "
            "authentication and PostgreSQL for the database..."
        )
        self.text_edit.setMinimumHeight(150)
        self.text_edit.textChanged.connect(self._on_text_changed)
        group_layout.addWidget(self.text_edit)

        layout.addWidget(group)

    def _on_text_changed(self):
        """Emit signal when text changes."""
        self.description_changed.emit(self.get_description())

    def get_description(self) -> str:
        """Get the current description text."""
        return self.text_edit.toPlainText().strip()

    def set_description(self, text: str):
        """Set the description text."""
        self.text_edit.setPlainText(text)

    def set_readonly(self, readonly: bool):
        """Enable or disable editing."""
        self.text_edit.setReadOnly(readonly)

    def clear(self):
        """Clear the description."""
        self.text_edit.clear()

    def is_empty(self) -> bool:
        """Check if description is empty."""
        return len(self.get_description()) == 0
