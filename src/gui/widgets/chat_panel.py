"""Chat panel for sending messages to LLM during workflow execution."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QTextBrowser, QLabel, QCheckBox
from PySide6.QtCore import Signal, QTimer


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
        self._bot_activity_text = ""
        self._activity_frame_index = 0
        self._activity_frames = ["[=     ]", "[==    ]", "[===   ]", "[ ===  ]", "[  === ]", "[   ===]", "[    ==]", "[     =]"]
        self._activity_timer = QTimer(self)
        self._activity_timer.setInterval(180)
        self._activity_timer.timeout.connect(self._advance_activity_frame)
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
        message_data = {
            "id": message_id,
            "role": "user",
            "content": content,
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

    def add_bot_message(self, content: str):
        """Add a standalone bot message to the history."""
        self.message_history.append({
            "id": f"bot_{len(self.message_history)}",
            "role": "bot",
            "content": content,
            "status": "completed"
        })
        self._update_display()

    def set_bot_activity(self, activity_text: str = ""):
        """Show or hide animated bot activity status."""
        self._bot_activity_text = activity_text.strip()
        if self._bot_activity_text:
            if not self._activity_timer.isActive():
                self._activity_timer.start()
        else:
            self._activity_timer.stop()
            self._activity_frame_index = 0
        self._update_display()

    def clear_bot_activity(self):
        """Clear animated bot activity indicator."""
        self.set_bot_activity("")

    def _advance_activity_frame(self):
        """Advance the activity animation frame."""
        if not self._bot_activity_text:
            return
        self._activity_frame_index = (self._activity_frame_index + 1) % len(self._activity_frames)
        self._update_display()

    def _update_display(self):
        """Refresh the HTML display of all messages."""
        html = "<div style='font-family: \"Segoe UI Variable Text\", sans-serif; color: #ece6de;'>"

        if not self.message_history and not self._bot_activity_text:
            html += "<p style='color: #9aa4b1; font-style: italic;'>No messages yet.</p>"
        else:
            for msg in self.message_history:
                status_color = {
                    "queued": "#9aa4b1",
                    "processing": "#58a6d8",
                    "completed": "#63b56e",
                    "failed": "#d07d7d"
                }.get(msg["status"], "#9aa4b1")

                if msg.get("role") == "bot":
                    html += self._render_bubble(
                        label="Agent",
                        content=msg.get("content", ""),
                        bubble_color="#1a232d",
                        border_color="#2e4b63",
                        label_color="#8ec5f0",
                        align="left"
                    )
                    continue

                html += self._render_bubble(
                    label="You",
                    content=msg.get("content", ""),
                    bubble_color="#1f3448",
                    border_color="#335a79",
                    label_color="#b8daff",
                    align="right"
                )

                html += f"""
                <div style='margin-top: 2px; margin-bottom: 8px; text-align: right; color: {status_color}; font-size: 11px;'>
                    {self._escape_html(msg['status'])}
                </div>
                """

                if "answer" in msg:
                    html += self._render_bubble(
                        label="Agent",
                        content=msg["answer"],
                        bubble_color="#1a232d",
                        border_color="#2e4b63",
                        label_color="#8ec5f0",
                        align="left"
                    )

            if self._bot_activity_text:
                frame = self._activity_frames[self._activity_frame_index]
                html += self._render_bubble(
                    label="Agent",
                    content=f"{self._bot_activity_text} {frame}",
                    bubble_color="#17212a",
                    border_color="#284055",
                    label_color="#8ec5f0",
                    align="left",
                    is_italic=True
                )

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

    def _render_bubble(self, label: str, content: str, bubble_color: str, border_color: str,
                       label_color: str, align: str = "left", is_italic: bool = False) -> str:
        """Render a single chat bubble row."""
        margin_side = "margin-right: 20%;" if align == "left" else "margin-left: 20%;"
        text_align = "left" if align == "left" else "right"
        font_style = "font-style: italic;" if is_italic else ""
        return f"""
        <div style='margin-bottom: 8px; {margin_side} text-align: {text_align};'>
            <div style='display: inline-block; max-width: 100%; background: {bubble_color}; border: 1px solid {border_color}; border-radius: 12px; padding: 8px 10px;'>
                <div style='color: {label_color}; font-size: 11px; font-weight: 600; margin-bottom: 2px;'>{self._escape_html(label)}</div>
                <div style='color: #e8edf2; font-size: 13px; line-height: 1.4; {font_style}'>{self._escape_html(content)}</div>
            </div>
        </div>
        """
