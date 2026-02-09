"""Error recovery dialog for workflow errors."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QFrame, QMenu
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QAction

from ...core.error_context import ErrorInfo


class ErrorRecoveryDialog(QDialog):
    """
    Modal dialog shown when workflow errors occur.
    Provides three recovery options:
    - Retry Phase: Re-run the phase from the beginning
    - Skip to Next: Move to the next iteration
    - Send to LLM: Let an LLM analyze and fix the error
    """

    # Signals
    retry_requested = Signal()
    skip_requested = Signal()
    send_to_llm_requested = Signal(str)  # provider_name

    def __init__(self, parent, error_info: ErrorInfo):
        super().__init__(parent)
        self.error_info = error_info
        self.setWindowTitle("Workflow Error")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        # Disable manual close (Escape/X button) - force user to choose
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)

        self.setup_ui()

    def setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Phase name header
        phase_label = QLabel(f"Error in {self.error_info.phase.name.replace('_', ' ').title()} Phase")
        phase_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #f08c8c;
                padding: 8px;
                background-color: rgba(240, 140, 140, 0.1);
                border-radius: 4px;
            }
        """)
        layout.addWidget(phase_label)

        # Error summary section
        summary_label = QLabel("Summary:")
        summary_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(summary_label)

        summary_text = QLabel(self.error_info.error_summary)
        summary_text.setWordWrap(True)
        summary_text.setStyleSheet("""
            QLabel {
                padding: 8px;
                background-color: palette(base);
                border-radius: 4px;
                color: #e8edf3;
            }
        """)
        layout.addWidget(summary_text)

        # Expandable error details section
        self.details_frame = QFrame()
        self.details_frame.setVisible(False)
        details_layout = QVBoxLayout(self.details_frame)
        details_layout.setContentsMargins(0, 0, 0, 0)

        details_label = QLabel("Full Error Details:")
        details_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        details_layout.addWidget(details_label)

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setPlainText(self.error_info.full_traceback)

        # Use monospace font for traceback
        font = QFont("Consolas", 10)
        if not font.exactMatch():
            font = QFont("Courier New", 10)
        self.details_text.setFont(font)

        self.details_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3e3e3e;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        self.details_text.setMaximumHeight(200)
        details_layout.addWidget(self.details_text)

        layout.addWidget(self.details_frame)

        # Toggle details button
        self.toggle_button = QPushButton("▼ View Full Error Details")
        self.toggle_button.setFlat(True)
        self.toggle_button.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 4px;
                color: #7cc1f3;
                border: none;
            }
            QPushButton:hover {
                text-decoration: underline;
            }
        """)
        self.toggle_button.clicked.connect(self._toggle_details)
        layout.addWidget(self.toggle_button)

        # Iteration info (if applicable)
        if self.error_info.current_iteration > 0:
            iter_label = QLabel(
                f"Iteration: {self.error_info.current_iteration} of {self.error_info.max_iterations}"
            )
            iter_label.setStyleSheet("color: #90a0af; font-size: 12px;")
            layout.addWidget(iter_label)

        layout.addStretch()

        # Action prompt
        action_label = QLabel("What would you like to do?")
        action_label.setStyleSheet("font-weight: bold; margin-top: 12px;")
        layout.addWidget(action_label)

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        # Retry button
        self.retry_button = QPushButton("Retry Phase")
        self.retry_button.setShortcut("R")
        self.retry_button.setToolTip("Re-run the phase from the beginning (Shortcut: R)")
        self.retry_button.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
            QPushButton:pressed {
                background-color: #0a4d7a;
            }
        """)
        self.retry_button.clicked.connect(self._on_retry)
        button_layout.addWidget(self.retry_button)

        # Skip button
        self.skip_button = QPushButton("Skip to Next")
        self.skip_button.setShortcut("S")
        self.skip_button.setToolTip("Move to the next iteration (Shortcut: S)")
        self.skip_button.setStyleSheet("""
            QPushButton {
                background-color: #5e5e5e;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #6e6e6e;
            }
            QPushButton:pressed {
                background-color: #4e4e4e;
            }
        """)
        self.skip_button.clicked.connect(self._on_skip)
        button_layout.addWidget(self.skip_button)

        # Send to LLM button with dropdown
        self.llm_button = QPushButton("Send to LLM ▼")
        self.llm_button.setShortcut("L")
        self.llm_button.setToolTip("Let an LLM analyze and fix the error (Shortcut: L)")
        self.llm_button.setStyleSheet("""
            QPushButton {
                background-color: #7cc1f3;
                color: #1e1e1e;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #8cd1ff;
            }
            QPushButton:pressed {
                background-color: #6cb1d3;
            }
        """)
        self.llm_button.clicked.connect(self._on_send_to_llm)
        button_layout.addWidget(self.llm_button)

        layout.addLayout(button_layout)

    def _toggle_details(self):
        """Toggle visibility of error details section."""
        is_visible = self.details_frame.isVisible()
        self.details_frame.setVisible(not is_visible)

        if is_visible:
            self.toggle_button.setText("▼ View Full Error Details")
        else:
            self.toggle_button.setText("▲ Hide Full Error Details")

    def _on_retry(self):
        """Handle retry button click."""
        self.retry_requested.emit()
        self.accept()

    def _on_skip(self):
        """Handle skip button click."""
        self.skip_requested.emit()
        self.accept()

    def _on_send_to_llm(self):
        """Handle send to LLM button click - show provider menu."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2d2d2d;
                color: #e8edf3;
                border: 1px solid #3e3e3e;
            }
            QMenu::item:selected {
                background-color: #0e639c;
            }
        """)

        # Add provider options
        providers = ["claude", "gemini", "codex"]
        for provider in providers:
            action = QAction(provider.capitalize(), self)
            action.triggered.connect(lambda checked=False, p=provider: self._send_to_provider(p))
            menu.addAction(action)

        # Show menu below button
        menu.exec(self.llm_button.mapToGlobal(self.llm_button.rect().bottomLeft()))

    def _send_to_provider(self, provider: str):
        """Send error to specific LLM provider."""
        self.send_to_llm_requested.emit(provider)
        self.accept()

    def keyPressEvent(self, event):
        """Override to prevent Escape key from closing dialog."""
        if event.key() == Qt.Key_Escape:
            event.ignore()
        else:
            super().keyPressEvent(event)
