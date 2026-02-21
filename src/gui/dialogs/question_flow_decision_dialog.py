"""Modeless decision dialog shown after a Q&A rewrite completes."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout

from ..theme import animate_fade_in, polish_button


class ProductDescriptionEditDialog(QDialog):
    """Modal editor for directly updating product description text."""

    def __init__(self, description: str, parent=None):
        super().__init__(parent)
        self._edited_description = description
        self.setWindowTitle("Edit Product Description")
        self.setModal(True)
        self.resize(760, 520)
        self._setup_ui(description)

    def _setup_ui(self, description: str):
        layout = QVBoxLayout(self)

        message = QLabel("Edit the product description directly, then click Save.")
        message.setWordWrap(True)
        layout.addWidget(message)

        self._editor = QTextEdit()
        self._editor.setPlainText(description)
        layout.addWidget(self._editor, stretch=1)

        button_row = QHBoxLayout()
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        polish_button(cancel_button, "secondary")
        button_row.addWidget(cancel_button)

        save_button = QPushButton("Save")
        save_button.clicked.connect(self._on_save_clicked)
        polish_button(save_button, "primary")
        button_row.addWidget(save_button)

        layout.addLayout(button_row)

    def _on_save_clicked(self):
        self._edited_description = self._editor.toPlainText()
        self.accept()

    def get_description(self) -> str:
        return self._edited_description


class QuestionFlowDecisionDialog(QDialog):
    """Lets the user continue refining or start the main loop explicitly."""

    ask_more_requested = Signal()
    continue_requested = Signal()
    start_main_loop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._allow_close = False
        self._get_description = None
        self._set_description = None

        self.setWindowTitle("Refine Product Description")
        self.setModal(False)
        self.setWindowModality(Qt.NonModal)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.resize(640, 320)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        message = QLabel(
            "The product description has been updated.\n\n"
            "Choose one of the actions below."
        )
        message.setStyleSheet("font-size: 17px; line-height: 1.35;")
        message.setWordWrap(True)
        layout.addWidget(message)

        ask_more_button = QPushButton("Ask More Questions")
        ask_more_button.clicked.connect(self._on_ask_more_clicked)
        polish_button(ask_more_button, "secondary")
        layout.addWidget(ask_more_button)

        edit_description_button = QPushButton("Edit Product Description")
        edit_description_button.clicked.connect(self._on_edit_description_clicked)
        polish_button(edit_description_button, "secondary")
        layout.addWidget(edit_description_button)

        continue_button = QPushButton("Continue")
        continue_button.clicked.connect(self._on_continue_clicked)
        polish_button(continue_button, "secondary")
        layout.addWidget(continue_button)

        start_button = QPushButton("Start Main Loop")
        start_button.clicked.connect(self._on_start_clicked)
        polish_button(start_button, "primary")
        layout.addWidget(start_button)

        animate_fade_in(self, duration_ms=220)

    def set_description_callbacks(self, get_description, set_description):
        self._get_description = get_description
        self._set_description = set_description

    def _on_ask_more_clicked(self):
        self._allow_close = True
        self.ask_more_requested.emit()
        self.close()

    def _on_edit_description_clicked(self):
        if not callable(self._get_description) or not callable(self._set_description):
            return
        editor = ProductDescriptionEditDialog(self._get_description(), parent=self)
        if editor.exec() == QDialog.Accepted:
            self._set_description(editor.get_description())

    def _on_continue_clicked(self):
        self._allow_close = True
        self.continue_requested.emit()
        self.close()

    def _on_start_clicked(self):
        self._allow_close = True
        self.start_main_loop_requested.emit()
        self.close()

    def reject(self):
        """Require an explicit action to leave the decision state."""
        if self._allow_close:
            super().reject()

    def closeEvent(self, event: QCloseEvent):
        """Block manual close until a valid action is chosen."""
        if self._allow_close:
            super().closeEvent(event)
            return
        event.ignore()
