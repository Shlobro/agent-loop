"""Panel for displaying and answering LLM-generated questions."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QLabel,
    QButtonGroup, QRadioButton, QPushButton, QGroupBox, QFrame
)
from PySide6.QtCore import Signal, Qt
from typing import Dict, List, Any


class QuestionPanel(QWidget):
    """
    Dynamically renders questions from JSON and collects user answers.

    Expected JSON format:
    {
        "questions": [
            {"id": "q1", "question": "What platform?", "options": ["CLI", "GUI", "Web"]}
        ]
    }
    """

    answers_submitted = Signal(dict)  # {question_id: selected_option}
    answers_changed = Signal()  # Emitted when any answer changes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.questions_data: List[Dict[str, Any]] = []
        self.button_groups: Dict[str, QButtonGroup] = {}
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Group box
        self.group = QGroupBox("Clarifying Questions")
        group_layout = QVBoxLayout(self.group)

        # Placeholder label (shown when no questions)
        self.placeholder_label = QLabel(
            "Questions will appear here after you start the process.\n"
            "The LLM will generate questions to clarify your requirements."
        )
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setStyleSheet("color: gray; padding: 20px;")
        group_layout.addWidget(self.placeholder_label)

        # Scroll area for questions
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.hide()

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.scroll_content)

        group_layout.addWidget(self.scroll_area)

        # Submit button
        self.submit_button = QPushButton("Submit Answers")
        self.submit_button.clicked.connect(self._on_submit)
        self.submit_button.setEnabled(False)
        self.submit_button.hide()
        group_layout.addWidget(self.submit_button)

        layout.addWidget(self.group)

    def load_questions(self, questions_json: Dict[str, Any]):
        """Parse JSON and create radio button groups for each question."""
        self.clear_questions()
        self.questions_data = questions_json.get("questions", [])

        if not self.questions_data:
            return

        # Hide placeholder, show scroll area
        self.placeholder_label.hide()
        self.scroll_area.show()
        self.submit_button.show()

        for q in self.questions_data:
            q_id = q["id"]
            q_text = q["question"]
            options = q.get("options", [])

            # Create frame for this question
            q_frame = QFrame()
            q_frame.setFrameShape(QFrame.StyledPanel)
            q_frame.setStyleSheet("QFrame { background-color: palette(base); border-radius: 4px; padding: 8px; }")
            q_layout = QVBoxLayout(q_frame)

            # Question label
            label = QLabel(f"<b>{q_text}</b>")
            label.setWordWrap(True)
            q_layout.addWidget(label)

            # Radio buttons for options
            group = QButtonGroup(self)
            group.buttonClicked.connect(self._on_answer_changed)

            for option in options:
                radio = QRadioButton(option)
                group.addButton(radio)
                q_layout.addWidget(radio)

            self.button_groups[q_id] = group
            self.scroll_layout.addWidget(q_frame)

        # Add stretch at the end
        self.scroll_layout.addStretch()

        # Enable submit if all questions answered
        self._update_submit_button()

    def clear_questions(self):
        """Remove all question widgets."""
        # Clear the scroll layout
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.button_groups.clear()
        self.questions_data = []

        # Show placeholder again
        self.placeholder_label.show()
        self.scroll_area.hide()
        self.submit_button.hide()
        self.submit_button.setEnabled(False)

    def _on_answer_changed(self):
        """Handle answer selection change."""
        self._update_submit_button()
        self.answers_changed.emit()

    def _update_submit_button(self):
        """Enable submit button only when all questions are answered."""
        all_answered = all(
            group.checkedButton() is not None
            for group in self.button_groups.values()
        )
        self.submit_button.setEnabled(all_answered)

    def _on_submit(self):
        """Handle submit button click."""
        answers = self.get_answers()
        self.answers_submitted.emit(answers)

    def get_answers(self) -> Dict[str, str]:
        """Return current answers as {question_id: selected_option}."""
        answers = {}
        for q_id, group in self.button_groups.items():
            checked = group.checkedButton()
            if checked:
                answers[q_id] = checked.text()
        return answers

    def has_all_answers(self) -> bool:
        """Check if all questions have been answered."""
        return all(
            group.checkedButton() is not None
            for group in self.button_groups.values()
        )

    def set_readonly(self, readonly: bool):
        """Enable or disable interaction."""
        for group in self.button_groups.values():
            for button in group.buttons():
                button.setEnabled(not readonly)
        self.submit_button.setEnabled(not readonly and self.has_all_answers())

    def get_questions_count(self) -> int:
        """Return number of questions loaded."""
        return len(self.questions_data)
