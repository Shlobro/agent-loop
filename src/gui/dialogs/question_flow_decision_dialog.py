"""Modeless decision dialog shown after a Q&A rewrite completes."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout

from ..theme import animate_fade_in, polish_button


class QuestionFlowDecisionDialog(QDialog):
    """Lets the user continue refining or start the main loop explicitly."""

    ask_more_requested = Signal()
    start_main_loop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._allow_close = False

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
            "You can edit it in the main window as much as needed.\n"
            "When ready, choose one of the actions below."
        )
        message.setStyleSheet("font-size: 17px; line-height: 1.35;")
        message.setWordWrap(True)
        layout.addWidget(message)

        ask_more_button = QPushButton("Ask More Questions")
        ask_more_button.clicked.connect(self._on_ask_more_clicked)
        polish_button(ask_more_button, "secondary")
        layout.addWidget(ask_more_button)

        start_button = QPushButton("Start Main Loop")
        start_button.clicked.connect(self._on_start_clicked)
        polish_button(start_button, "primary")
        layout.addWidget(start_button)

        animate_fade_in(self, duration_ms=220)

    def _on_ask_more_clicked(self):
        self._allow_close = True
        self.ask_more_requested.emit()
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
