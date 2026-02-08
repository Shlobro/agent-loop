"""Panel for user project description input."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit, QTextBrowser,
    QHBoxLayout, QPushButton, QStackedWidget
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
        layout.setSpacing(8)

        self.prompt_label = QLabel("Product Description")
        self.prompt_label.setProperty("role", "hero")
        self.prompt_label.setWordWrap(True)
        layout.addWidget(self.prompt_label)

        self.text_edit = QTextEdit()
        self.text_edit.setStyleSheet("font-size: 17px;")
        self.text_edit.setMinimumHeight(300)
        self.text_edit.textChanged.connect(self._on_text_changed)

        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(True)
        self.preview.setMinimumHeight(300)

        self.mode_row_widget = QWidget()
        mode_row = QHBoxLayout(self.mode_row_widget)
        mode_row.setContentsMargins(0, 0, 0, 0)
        mode_label = QLabel("View")
        mode_label.setProperty("role", "muted")
        mode_row.addWidget(mode_label)

        self.edit_mode_button = QPushButton("Edit")
        self.edit_mode_button.setCheckable(True)
        self.edit_mode_button.clicked.connect(self._enter_edit_mode)
        mode_row.addWidget(self.edit_mode_button)

        self.preview_mode_button = QPushButton("Preview")
        self.preview_mode_button.setCheckable(True)
        self.preview_mode_button.clicked.connect(self._enter_preview_mode)
        mode_row.addWidget(self.preview_mode_button)

        mode_row.addStretch(1)
        layout.addWidget(self.mode_row_widget)

        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(self.text_edit)
        self.content_stack.addWidget(self.preview)
        layout.addWidget(self.content_stack)
        self._refresh_preview()
        self._set_mode(edit_mode=True)
        self.set_preview_controls_visible(False)

    def _on_text_changed(self):
        """Emit signal when text changes."""
        self._refresh_preview()
        self.description_changed.emit(self.get_description())

    def get_description(self) -> str:
        """Get the current description text."""
        return self.text_edit.toPlainText().strip()

    def set_description(self, text: str):
        """Set the description text."""
        self.text_edit.setPlainText(text)
        self._refresh_preview()

    def set_readonly(self, readonly: bool):
        """Enable or disable editing."""
        self.text_edit.setReadOnly(readonly)
        self.edit_mode_button.setEnabled(not readonly)
        if readonly:
            self._set_mode(edit_mode=False)
        elif not self.is_preview_mode():
            self._set_mode(edit_mode=True)

    def set_preview_controls_visible(self, visible: bool):
        """Show or hide explicit Edit/Preview controls."""
        self.mode_row_widget.setVisible(bool(visible))

    def set_preview_mode(self, enabled: bool):
        """Switch between edit and markdown preview mode."""
        self._set_mode(edit_mode=not enabled)

    def is_preview_mode(self) -> bool:
        """Return True when markdown preview mode is active."""
        return self.content_stack.currentWidget() is self.preview

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
        self._refresh_preview()

    def is_empty(self) -> bool:
        """Check if description is empty."""
        return len(self.get_description()) == 0

    def _refresh_preview(self):
        """Render current description as Markdown preview."""
        markdown = self.get_description()
        if markdown:
            self.preview.setMarkdown(markdown)
            return
        self.preview.setMarkdown(
            "_Markdown preview appears here once the project description has content._"
        )

    def _set_mode(self, edit_mode: bool):
        self.content_stack.setCurrentWidget(self.text_edit if edit_mode else self.preview)
        self.edit_mode_button.setChecked(edit_mode)
        self.preview_mode_button.setChecked(not edit_mode)

    def _enter_edit_mode(self):
        self._set_mode(edit_mode=True)

    def _enter_preview_mode(self):
        self._set_mode(edit_mode=False)
