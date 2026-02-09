"""Dialog to show LLM error fix conclusion."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


class ErrorConclusionDialog(QDialog):
    """
    Modal dialog to show the contents of error-conclusion.md after LLM error fix.
    If the conclusion is empty, prompts user to try a different approach.
    """

    retry_requested = Signal()
    try_different_llm_requested = Signal()
    skip_requested = Signal()

    def __init__(self, parent, conclusion: str, provider_name: str):
        super().__init__(parent)
        self.conclusion = conclusion
        self.provider_name = provider_name
        self.setWindowTitle("Error Fix Conclusion")
        self.setModal(True)
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)

        self.setup_ui()

    def setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        is_empty = not self.conclusion or self.conclusion.strip() == ""

        if is_empty:
            # Show failure message
            self._setup_failure_ui(layout)
        else:
            # Show success message and conclusion
            self._setup_success_ui(layout)

    def _setup_failure_ui(self, layout):
        """Setup UI for when LLM failed to write conclusion."""
        # Failure header
        failure_label = QLabel(f"{self.provider_name.capitalize()} Failed to Fix Error")
        failure_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #f08c8c;
                padding: 8px;
                background-color: rgba(240, 140, 140, 0.1);
                border-radius: 4px;
            }
        """)
        layout.addWidget(failure_label)

        # Explanation
        explanation = QLabel(
            f"The {self.provider_name.capitalize()} LLM did not write anything to error-conclusion.md. "
            "This may indicate that the error fix attempt failed or the LLM encountered an issue."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("padding: 8px; color: #e8edf3;")
        layout.addWidget(explanation)

        layout.addStretch()

        # Action prompt
        action_label = QLabel("What would you like to do?")
        action_label.setStyleSheet("font-weight: bold; margin-top: 12px;")
        layout.addWidget(action_label)

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        # Try different LLM button
        self.try_llm_button = QPushButton("Try Different LLM")
        self.try_llm_button.setToolTip("Choose a different LLM provider to attempt the fix")
        self.try_llm_button.setStyleSheet("""
            QPushButton {
                background-color: #7cc1f3;
                color: #1e1e1e;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 140px;
            }
            QPushButton:hover {
                background-color: #8cd1ff;
            }
            QPushButton:pressed {
                background-color: #6cb1d3;
            }
        """)
        self.try_llm_button.clicked.connect(self._on_try_different_llm)
        button_layout.addWidget(self.try_llm_button)

        # Retry manual button
        self.retry_button = QPushButton("Retry Phase")
        self.retry_button.setToolTip("Re-run the phase from the beginning")
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
        self.skip_button.setToolTip("Move to the next iteration")
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

        layout.addLayout(button_layout)

    def _setup_success_ui(self, layout):
        """Setup UI for when LLM successfully wrote conclusion."""
        # Success header
        success_label = QLabel(f"{self.provider_name.capitalize()} Error Fix Conclusion")
        success_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #86d9a0;
                padding: 8px;
                background-color: rgba(134, 217, 160, 0.1);
                border-radius: 4px;
            }
        """)
        layout.addWidget(success_label)

        # Conclusion content
        conclusion_label = QLabel("The LLM's analysis and fix:")
        conclusion_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(conclusion_label)

        self.conclusion_text = QTextEdit()
        self.conclusion_text.setReadOnly(True)
        self.conclusion_text.setPlainText(self.conclusion)

        # Use a readable font
        font = QFont("Segoe UI", 10)
        self.conclusion_text.setFont(font)

        self.conclusion_text.setStyleSheet("""
            QTextEdit {
                background-color: #2d2d2d;
                color: #e8edf3;
                border: 1px solid #3e3e3e;
                border-radius: 4px;
                padding: 12px;
            }
        """)
        layout.addWidget(self.conclusion_text)

        # Action prompt
        action_label = QLabel("Would you like to retry the phase with these fixes?")
        action_label.setStyleSheet("font-weight: bold; margin-top: 12px;")
        layout.addWidget(action_label)

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        # Retry button
        self.retry_button = QPushButton("Retry Phase")
        self.retry_button.setDefault(True)
        self.retry_button.setToolTip("Re-run the phase with the LLM's fixes")
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

        # Try different LLM button
        self.try_llm_button = QPushButton("Try Different LLM")
        self.try_llm_button.setToolTip("Choose a different LLM provider to attempt the fix")
        self.try_llm_button.setStyleSheet("""
            QPushButton {
                background-color: #7cc1f3;
                color: #1e1e1e;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 140px;
            }
            QPushButton:hover {
                background-color: #8cd1ff;
            }
            QPushButton:pressed {
                background-color: #6cb1d3;
            }
        """)
        self.try_llm_button.clicked.connect(self._on_try_different_llm)
        button_layout.addWidget(self.try_llm_button)

        # Skip button
        self.skip_button = QPushButton("Skip to Next")
        self.skip_button.setToolTip("Move to the next iteration without retrying")
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

        layout.addLayout(button_layout)

    def _on_retry(self):
        """Handle retry button click."""
        self.retry_requested.emit()
        self.accept()

    def _on_try_different_llm(self):
        """Handle try different LLM button click."""
        self.try_different_llm_requested.emit()
        self.accept()

    def _on_skip(self):
        """Handle skip button click."""
        self.skip_requested.emit()
        self.accept()
