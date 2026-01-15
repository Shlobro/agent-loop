"""Panel for displaying and answering LLM-generated questions."""

from typing import List, Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QButtonGroup, QRadioButton,
    QPushButton, QGroupBox, QHBoxLayout, QTextEdit, QScrollArea,
    QFrame
)
from PySide6.QtCore import Signal, Qt


class QuestionPanel(QWidget):
    """
    Displays one question at a time and collects a single answer.
    """

    answer_submitted = Signal(str, str)  # (question_text, answer_text)
    stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_question_text = ""
        self.option_group = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.group = QGroupBox("Clarifying Questions")
        self.group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 5px 10px;
            }
        """)
        group_layout = QVBoxLayout(self.group)
        group_layout.setSpacing(10)

        self.placeholder_label = QLabel(
            "Questions will appear here after you start the process.\n"
            "The LLM will generate questions to clarify your requirements."
        )
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setStyleSheet("color: gray; padding: 30px; font-size: 13px;")
        group_layout.addWidget(self.placeholder_label)

        self.content_frame = QFrame()
        self.content_frame.setFrameShape(QFrame.NoFrame)
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setSpacing(8)

        self.counter_label = QLabel("")
        self.counter_label.setStyleSheet("color: gray; font-size: 12px;")
        self.content_layout.addWidget(self.counter_label)

        self.question_label = QLabel("")
        self.question_label.setWordWrap(True)
        self.question_label.setStyleSheet("font-size: 13px; font-weight: bold; padding: 4px 0;")
        self.content_layout.addWidget(self.question_label)

        self.options_container = QWidget()
        self.options_layout = QVBoxLayout(self.options_container)
        self.options_layout.setSpacing(6)
        self.content_layout.addWidget(self.options_container)

        self.freeform_label = QLabel("Or type your own answer:")
        self.freeform_label.setStyleSheet("font-size: 12px;")
        self.content_layout.addWidget(self.freeform_label)

        self.freeform_edit = QTextEdit()
        self.freeform_edit.setPlaceholderText("Type your answer here...")
        self.freeform_edit.setMinimumHeight(70)
        self.freeform_edit.textChanged.connect(self._on_answer_changed)
        self.content_layout.addWidget(self.freeform_edit)

        button_row = QHBoxLayout()
        self.submit_button = QPushButton("Submit Answer")
        self.submit_button.setMinimumHeight(36)
        self.submit_button.clicked.connect(self._on_submit)
        self.submit_button.setEnabled(False)
        button_row.addWidget(self.submit_button)

        self.stop_button = QPushButton("Stop Getting More Questions")
        self.stop_button.setMinimumHeight(36)
        self.stop_button.clicked.connect(self.stop_requested.emit)
        button_row.addWidget(self.stop_button)

        self.content_layout.addLayout(button_row)

        self.previous_group = QGroupBox("Previous Answers")
        self.previous_group.setStyleSheet("font-size: 12px; font-weight: bold;")
        previous_layout = QVBoxLayout(self.previous_group)

        self.previous_scroll = QScrollArea()
        self.previous_scroll.setWidgetResizable(True)
        self.previous_scroll.setFrameShape(QFrame.NoFrame)
        previous_layout.addWidget(self.previous_scroll)

        self.previous_label = QLabel("")
        self.previous_label.setWordWrap(True)
        self.previous_label.setStyleSheet("font-size: 12px; padding: 4px;")
        self.previous_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        previous_content = QWidget()
        previous_content_layout = QVBoxLayout(previous_content)
        previous_content_layout.setContentsMargins(0, 0, 0, 0)
        previous_content_layout.addWidget(self.previous_label)
        self.previous_scroll.setWidget(previous_content)

        self.content_layout.addWidget(self.previous_group)

        group_layout.addWidget(self.content_frame)
        self.content_frame.hide()
        self.previous_group.hide()

        layout.addWidget(self.group)

    def show_question(self, question_text: str, options: List[str],
                      question_num: int, total: int):
        """Display a single question and reset the inputs."""
        self.current_question_text = question_text
        self.counter_label.setText(f"Question {question_num} of {total}")
        self.question_label.setText(question_text)

        self._clear_options()
        self.option_group = QButtonGroup(self)
        self.option_group.setExclusive(True)
        self.option_group.buttonClicked.connect(self._on_answer_changed)

        if options:
            for option in options:
                radio = QRadioButton(option)
                radio.setStyleSheet("""
                    QRadioButton {
                        font-size: 12px;
                        padding: 4px;
                        spacing: 8px;
                    }
                    QRadioButton::indicator {
                        width: 16px;
                        height: 16px;
                    }
                """)
                self.option_group.addButton(radio)
                self.options_layout.addWidget(radio)
        else:
            no_options = QLabel("No preset options provided.")
            no_options.setStyleSheet("color: gray; font-size: 12px;")
            self.options_layout.addWidget(no_options)

        self.freeform_edit.clear()
        self.submit_button.setEnabled(False)

        self.placeholder_label.hide()
        self.content_frame.show()

    def show_previous_qa(self, qa_pairs: List[Dict[str, str]]):
        """Show the list of prior Q&A pairs."""
        if not qa_pairs:
            self.previous_group.hide()
            return

        lines = []
        for i, qa in enumerate(qa_pairs, 1):
            question = qa.get("question", "")
            answer = qa.get("answer", "")
            lines.append(f"Q{i}: {question}")
            lines.append(f"A{i}: {answer}")
            lines.append("")

        self.previous_label.setText("\n".join(lines).strip())
        self.previous_group.show()

    def clear_question(self):
        """Reset the panel to its empty state."""
        self.current_question_text = ""
        self._clear_options()
        self.freeform_edit.clear()
        self.submit_button.setEnabled(False)
        self.content_frame.hide()
        self.previous_group.hide()
        self.placeholder_label.show()

    def set_readonly(self, readonly: bool):
        """Enable or disable interaction."""
        if self.option_group:
            for button in self.option_group.buttons():
                button.setEnabled(not readonly)
        self.freeform_edit.setReadOnly(readonly)
        if readonly:
            self.submit_button.setEnabled(False)
        else:
            self._update_submit_button()
        self.stop_button.setEnabled(not readonly)

    def _clear_options(self):
        """Clear current option widgets."""
        if self.option_group:
            self.option_group.deleteLater()
            self.option_group = None
        while self.options_layout.count():
            item = self.options_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_answer_changed(self):
        """Handle changes in selected option or freeform input."""
        self._update_submit_button()

    def _update_submit_button(self):
        """Enable submit if any answer is provided."""
        self.submit_button.setEnabled(bool(self.get_current_answer()))

    def _on_submit(self):
        """Handle submit button click."""
        answer = self.get_current_answer()
        if not answer:
            return
        self.answer_submitted.emit(self.current_question_text, answer)

    def get_current_answer(self) -> str:
        """Return the selected option or freeform input (freeform takes priority)."""
        freeform = self.freeform_edit.toPlainText().strip()
        if freeform:
            return freeform
        if self.option_group:
            checked = self.option_group.checkedButton()
            if checked:
                return checked.text().strip()
        return ""
