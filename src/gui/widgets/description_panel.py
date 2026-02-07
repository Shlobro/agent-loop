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
        group.setObjectName("descriptionGroup")
        group_layout = QVBoxLayout(group)

        # Instructions label
        instructions = QLabel(
            "Describe what you want to build. Be specific about features, "
            "requirements, and any technical constraints."
        )
        instructions.setWordWrap(True)
        instructions.setProperty("role", "muted")
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

    def append_qa_pairs(self, qa_pairs: list):
        """Append answered clarifying questions to the description text."""
        if not qa_pairs:
            return
        current = self.text_edit.toPlainText().rstrip()
        lines = [current] if current else []
        if current:
            lines.append("")
        lines.append("Clarifying Questions and Answers:")
        for i, qa in enumerate(qa_pairs, 1):
            question = str(qa.get("question", "")).strip()
            answer = str(qa.get("answer", "")).strip()
            if question and answer:
                lines.append(f"Q{i}: {question}")
                lines.append(f"A{i}: {answer}")
        self.set_description("\n".join(lines).rstrip())

    def clear(self):
        """Clear the description."""
        self.text_edit.clear()

    def is_empty(self) -> bool:
        """Check if description is empty."""
        return len(self.get_description()) == 0
