"""Chat panel for sending messages to LLM during workflow execution."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QTextBrowser, QLabel, QCheckBox
from PySide6.QtCore import Signal
from datetime import datetime


class ChatPanel(QWidget):
    """
    Chat interface for client messages during workflow execution.

    Provides message input, send button, message history display,
    and checkboxes to control LLM behavior (update description, add tasks, provide answer).
    """

    message_sent = Signal(str, bool, bool, bool)  # Emits: message, update_desc, add_tasks, provide_answer

    def __init__(self):
        super().__init__()
        self.message_history = []  # List of message dicts
        self.setup_ui()

    def setup_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        # Header
        header = QLabel("Client Messages")
        header.setProperty("role", "hero_subtitle")
        layout.addWidget(header)

        # Message history display
        self.history_browser = QTextBrowser()
        self.history_browser.setOpenExternalLinks(False)
        self.history_browser.setMinimumHeight(200)
        layout.addWidget(self.history_browser, stretch=2)

        # Input area
        input_label = QLabel("Send message to LLM:")
        input_label.setProperty("role", "muted")
        layout.addWidget(input_label)

        self.input_area = QTextEdit()
        self.input_area.setPlaceholderText("Enter your project description here...")
        self.input_area.setMaximumHeight(100)
        layout.addWidget(self.input_area, stretch=1)

        # Checkboxes for controlling LLM behavior
        checkbox_layout = QHBoxLayout()
        checkbox_layout.setSpacing(15)

        self.update_description_cb = QCheckBox("Update description")
        self.update_description_cb.setToolTip("Update product-description.md with information from the message")
        checkbox_layout.addWidget(self.update_description_cb)

        self.add_tasks_cb = QCheckBox("Add tasks")
        self.add_tasks_cb.setToolTip("Add new tasks to tasks.md based on the message")
        checkbox_layout.addWidget(self.add_tasks_cb)

        self.provide_answer_cb = QCheckBox("Provide answer in text")
        self.provide_answer_cb.setToolTip("Write a response to the client in answer.md")
        checkbox_layout.addWidget(self.provide_answer_cb)

        checkbox_layout.addStretch()
        layout.addLayout(checkbox_layout)

        # Send button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.send_button = QPushButton("Send Message")
        self.send_button.setProperty("variant", "primary")
        self.send_button.clicked.connect(self._on_send_clicked)
        button_layout.addWidget(self.send_button)
        layout.addLayout(button_layout)

        # Initial display
        self._update_display()

    def _on_send_clicked(self):
        """Handle send button click."""
        message = self.input_area.toPlainText().strip()
        if not message:
            return

        # Get checkbox states
        update_desc = self.update_description_cb.isChecked()
        add_tasks = self.add_tasks_cb.isChecked()
        provide_answer = self.provide_answer_cb.isChecked()

        # Emit signal with checkbox states
        self.message_sent.emit(message, update_desc, add_tasks, provide_answer)

        # Clear input and reset checkboxes
        self.input_area.clear()
        self.update_description_cb.setChecked(False)
        self.add_tasks_cb.setChecked(False)
        self.provide_answer_cb.setChecked(False)

    def add_message(self, message_id: str, content: str, status: str = "queued"):
        """Add a message to the history display."""
        timestamp = datetime.now().strftime("%H:%M:%S")

        message_data = {
            "id": message_id,
            "content": content,
            "timestamp": timestamp,
            "status": status
        }
        self.message_history.append(message_data)
        self._update_display()

    def update_message_status(self, message_id: str, status: str):
        """Update status of a message (queued/processing/completed)."""
        for msg in self.message_history:
            if msg["id"] == message_id:
                msg["status"] = status
                break
        self._update_display()

    def add_answer(self, message_id: str, answer_content: str):
        """Add answer content for a message."""
        for msg in self.message_history:
            if msg["id"] == message_id:
                msg["answer"] = answer_content
                break
        self._update_display()

    def _update_display(self):
        """Refresh the HTML display of all messages."""
        html = "<div style='font-family: \"Segoe UI Variable Text\", sans-serif; color: #ece6de;'>"

        if not self.message_history:
            html += "<p style='color: #9aa4b1; font-style: italic;'>No messages yet. Send a message to interact with the LLM during execution.</p>"
        else:
            for msg in self.message_history:
                status_icon = {
                    "queued": "⏳",
                    "processing": "⚙️",
                    "completed": "✓"
                }.get(msg["status"], "•")

                status_color = {
                    "queued": "#9aa4b1",
                    "processing": "#4f95c7",
                    "completed": "#53b8b2"
                }.get(msg["status"], "#9aa4b1")

                html += f"""
                <div style='margin-bottom: 20px; padding: 12px; background: #151a1f; border-radius: 10px; border: 1px solid #232a31;'>
                    <div style='color: {status_color}; font-size: 12px; margin-bottom: 6px; font-weight: 600;'>
                        {status_icon} {msg['timestamp']} - {msg['status'].upper()}
                    </div>
                    <div style='color: #ece6de; font-size: 14px; margin-bottom: 6px;'>
                        <strong style='color: #c9d3dd;'>You:</strong> {self._escape_html(msg['content'])}
                    </div>
                """

                if "answer" in msg:
                    html += f"""
                    <div style='margin-top: 10px; padding: 10px; background: #0f1419; border-left: 3px solid #2b77ae; border-radius: 6px;'>
                        <div style='color: #4f95c7; font-size: 12px; margin-bottom: 6px; font-weight: 600;'>LLM Response:</div>
                        <div style='color: #ece6de; font-size: 14px; line-height: 1.5;'>{self._escape_html(msg['answer'])}</div>
                    </div>
                    """

                html += "</div>"

        html += "</div>"
        self.history_browser.setHtml(html)

        # Scroll to bottom
        scrollbar = self.history_browser.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#39;")
                .replace("\n", "<br>"))

    def set_input_enabled(self, enabled: bool):
        """Enable/disable message input."""
        self.input_area.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        self.update_description_cb.setEnabled(enabled)
        self.add_tasks_cb.setEnabled(enabled)
        self.provide_answer_cb.setEnabled(enabled)

    def update_placeholder_text(self, has_description: bool):
        """Update placeholder text based on whether product description exists."""
        if has_description:
            self.input_area.setPlaceholderText("Ask a question or request changes...")
        else:
            self.input_area.setPlaceholderText("Enter your project description here...")
