"""Scrollable log viewer with color-coded output."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPlainTextEdit, QGroupBox,
    QHBoxLayout, QPushButton, QComboBox
)
from PySide6.QtCore import Slot, Qt
from PySide6.QtGui import QTextCharFormat, QColor, QFont
from datetime import datetime


class LogViewer(QWidget):
    """
    Scrollable log viewer with color-coded output based on level.
    Supports filtering by log level.
    """

    # Color scheme for different log levels
    COLORS = {
        "info": "#e8edf3",
        "success": "#86d9a0",
        "warning": "#e6c078",
        "error": "#f08c8c",
        "llm_output": "#7cc1f3",
        "phase": "#9db9ff",
        "debug": "#90a0af",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.auto_scroll = True
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Output Log")
        group_layout = QVBoxLayout(group)

        # Toolbar
        toolbar = QHBoxLayout()

        # Filter dropdown
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("All", "all")
        self.filter_combo.addItem("Info & Above", "info")
        self.filter_combo.addItem("Warnings & Errors", "warning")
        self.filter_combo.addItem("Errors Only", "error")
        self.filter_combo.addItem("LLM Stream", "llm_output")
        toolbar.addWidget(self.filter_combo)

        toolbar.addStretch()

        # Clear button
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear)
        toolbar.addWidget(self.clear_button)

        # Auto-scroll toggle
        self.auto_scroll_button = QPushButton("Follow: ON")
        self.auto_scroll_button.setCheckable(True)
        self.auto_scroll_button.setChecked(True)
        self.auto_scroll_button.clicked.connect(self._toggle_auto_scroll)
        toolbar.addWidget(self.auto_scroll_button)

        group_layout.addLayout(toolbar)

        # Log text area
        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setMaximumBlockCount(10000)  # Limit memory usage
        self.text_edit.setLineWrapMode(QPlainTextEdit.WidgetWidth)

        # Use monospace font
        font = QFont("Consolas", 9)
        if not font.exactMatch():
            font = QFont("Courier New", 9)
        self.text_edit.setFont(font)

        group_layout.addWidget(self.text_edit)
        layout.addWidget(group)

    def _toggle_auto_scroll(self):
        """Toggle auto-scroll behavior."""
        self.auto_scroll = self.auto_scroll_button.isChecked()
        self.auto_scroll_button.setText(
            f"Follow: {'ON' if self.auto_scroll else 'OFF'}"
        )

    @Slot(str, str)
    def append_log(self, message: str, level: str = "info"):
        """
        Append message with timestamp and color based on level.

        Args:
            message: The log message
            level: One of 'info', 'success', 'warning', 'error', 'llm_output', 'phase', 'debug'
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = self.COLORS.get(level, self.COLORS["info"])

        # Format the message with HTML
        level_indicator = level.upper()[:3] if level != "llm_output" else "LLM"
        formatted = f'<span style="color:{color}">[{timestamp}] [{level_indicator}] {self._escape_html(message)}</span>'

        self.text_edit.appendHtml(formatted)

        # Auto-scroll to bottom
        if self.auto_scroll:
            scrollbar = self.text_edit.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#39;"))

    @Slot(str)
    def append_llm_output(self, line: str):
        """Convenience method for LLM output."""
        self.append_log(line, "llm_output")

    @Slot(str)
    def append_phase(self, message: str):
        """Convenience method for phase changes."""
        self.append_log(f"=== {message} ===", "phase")

    @Slot(str)
    def append_success(self, message: str):
        """Convenience method for success messages."""
        self.append_log(message, "success")

    @Slot(str)
    def append_warning(self, message: str):
        """Convenience method for warnings."""
        self.append_log(message, "warning")

    @Slot(str)
    def append_error(self, message: str):
        """Convenience method for errors."""
        self.append_log(message, "error")

    def clear(self):
        """Clear all log content."""
        self.text_edit.clear()

    def get_content(self) -> str:
        """Get all log content as plain text."""
        return self.text_edit.toPlainText()

    def save_to_file(self, filepath: str):
        """Save log content to a file."""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.get_content())
