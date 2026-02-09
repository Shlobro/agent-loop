"""Dialog for displaying LLM answers to client messages."""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton, QHBoxLayout, QApplication, QLabel
from PySide6.QtCore import Qt


class AnswerDisplayDialog(QDialog):
    """
    Modal dialog to display LLM's answer to a client message.

    Shows Markdown-rendered answer with copy-to-clipboard option.
    """

    def __init__(self, answer_content: str, parent=None):
        super().__init__(parent)
        self.answer_content = answer_content
        self.setup_ui()

    def setup_ui(self):
        """Initialize UI components."""
        self.setWindowTitle("LLM Response")
        self.setMinimumSize(600, 400)
        self.setWindowModality(Qt.ApplicationModal)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QLabel("The LLM has responded to your message:")
        header.setProperty("role", "hero_subtitle")
        layout.addWidget(header)

        # Answer display
        self.text_browser = QTextBrowser()
        self.text_browser.setMarkdown(self.answer_content)
        self.text_browser.setOpenExternalLinks(False)
        layout.addWidget(self.text_browser)

        # Buttons
        button_layout = QHBoxLayout()

        copy_button = QPushButton("Copy to Clipboard")
        copy_button.clicked.connect(self._copy_to_clipboard)
        button_layout.addWidget(copy_button)

        button_layout.addStretch()

        continue_button = QPushButton("Continue")
        continue_button.setProperty("variant", "primary")
        continue_button.clicked.connect(self.accept)
        continue_button.setDefault(True)
        button_layout.addWidget(continue_button)

        layout.addLayout(button_layout)

    def _copy_to_clipboard(self):
        """Copy answer content to clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.answer_content)
