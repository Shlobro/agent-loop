"""Panel for displaying and answering LLM-generated questions."""

from functools import partial
from typing import List, Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QButtonGroup, QRadioButton,
    QPushButton, QGroupBox, QHBoxLayout, QTextEdit, QScrollArea,
    QFrame, QStackedWidget
)
from PySide6.QtCore import Signal, Qt


class QuestionPanel(QWidget):
    """
    Displays a batch of questions at once and collects answers.
    """

    answers_submitted = Signal(list)  # [{"question": str, "answer": str}]
    generate_again_requested = Signal()
    start_planning_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.question_entries: List[Dict[str, object]] = []
        self.activity_mode = False
        self.current_index = 0
        self.submitted = False
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

        self.activity_frame = QFrame()
        self.activity_frame.setFrameShape(QFrame.NoFrame)
        self.activity_layout = QVBoxLayout(self.activity_frame)
        self.activity_layout.setSpacing(6)

        self.activity_phase_label = QLabel("")
        self.activity_action_label = QLabel("")
        self.activity_agent_label = QLabel("")
        self.activity_review_label = QLabel("")
        self.activity_findings_label = QLabel("")

        activity_labels = [
            self.activity_phase_label,
            self.activity_action_label,
            self.activity_agent_label,
            self.activity_review_label,
            self.activity_findings_label,
        ]
        for label in activity_labels:
            label.setStyleSheet("font-size: 12px; color: #444444;")
            label.setWordWrap(True)
            self.activity_layout.addWidget(label)

        self.activity_frame.hide()
        group_layout.addWidget(self.activity_frame)

        self.content_frame = QFrame()
        self.content_frame.setFrameShape(QFrame.NoFrame)
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setSpacing(8)

        self.counter_label = QLabel("")
        self.counter_label.setStyleSheet("color: gray; font-size: 12px;")
        self.content_layout.addWidget(self.counter_label)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: gray; font-size: 12px; font-style: italic; padding: 4px 0;")
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        self.content_layout.addWidget(self.status_label)

        self.questions_scroll = QScrollArea()
        self.questions_scroll.setWidgetResizable(True)
        self.questions_scroll.setFrameShape(QFrame.NoFrame)
        self.questions_stack = QStackedWidget()
        self.questions_scroll.setWidget(self.questions_stack)
        self.content_layout.addWidget(self.questions_scroll)

        navigation_row = QHBoxLayout()
        self.prev_question_button = QPushButton("Previous Question")
        self.prev_question_button.setMinimumHeight(32)
        self.prev_question_button.clicked.connect(self._on_previous_question)
        self.prev_question_button.setEnabled(False)
        navigation_row.addWidget(self.prev_question_button)

        self.next_question_button = QPushButton("Next Question")
        self.next_question_button.setMinimumHeight(32)
        self.next_question_button.clicked.connect(self._on_next_question)
        self.next_question_button.setEnabled(False)
        navigation_row.addWidget(self.next_question_button)

        self.content_layout.addLayout(navigation_row)

        button_row = QHBoxLayout()

        self.submit_button = QPushButton("Submit Answers")
        self.submit_button.setMinimumHeight(36)
        self.submit_button.clicked.connect(self._on_submit)
        self.submit_button.setEnabled(False)
        self.submit_button.setVisible(True)
        button_row.addWidget(self.submit_button)

        self.generate_again_button = QPushButton("Generate More Questions")
        self.generate_again_button.setMinimumHeight(36)
        self.generate_again_button.clicked.connect(self._on_generate_again)
        self.generate_again_button.setEnabled(False)
        self.generate_again_button.setVisible(True)
        button_row.addWidget(self.generate_again_button)

        self.start_planning_button = QPushButton("Start Planning")
        self.start_planning_button.setMinimumHeight(36)
        self.start_planning_button.clicked.connect(self._on_start_planning)
        self.start_planning_button.setEnabled(False)
        self.start_planning_button.setVisible(False)
        button_row.addWidget(self.start_planning_button)

        self.content_layout.addLayout(button_row)

        group_layout.addWidget(self.content_frame)
        self.content_frame.hide()

        layout.addWidget(self.group)

    def show_questions(self, questions: List[Dict[str, object]]):
        """Display a batch of questions and reset inputs."""
        self._set_mode_questions()
        self._clear_questions()
        self.submitted = False

        total = len(questions)
        self._set_counter_label(0, total)
        self.status_label.setText("Answer the questions below.")
        self.status_label.show()

        for index, question in enumerate(questions, 1):
            question_text = str(question.get("question", "")).strip()
            options = question.get("options") or []
            self._add_question_entry(index, question_text, options)

        self.submit_button.setEnabled(False)
        self.submit_button.setVisible(True)
        self.generate_again_button.setEnabled(False)
        self.start_planning_button.setEnabled(False)
        self.start_planning_button.setVisible(False)
        self.prev_question_button.setVisible(True)
        self.next_question_button.setVisible(True)
        self._set_current_question(0)
        self._update_navigation_state()

        self.placeholder_label.hide()
        self.content_frame.show()

    def show_answers_saved(self):
        """Show a post-answer state that prompts for the next action."""
        self._set_mode_questions()
        self._set_questions_readonly(True)
        self.status_label.setText("Answers saved. Generate more questions or start planning.")
        self.status_label.show()
        self.submit_button.setEnabled(False)
        self.generate_again_button.setEnabled(True)
        self.start_planning_button.setEnabled(True)
        self.start_planning_button.setVisible(True)
        self.submit_button.setVisible(False)
        self.prev_question_button.setEnabled(False)
        self.prev_question_button.setVisible(False)
        self.next_question_button.setEnabled(False)
        self.next_question_button.setVisible(False)
        self.submitted = True

    def show_updating_description(self, message: str = "Updating project description..."):
        """Show a waiting message while the description is updated."""
        self._set_mode_questions()
        self._set_questions_readonly(True)
        self.status_label.setText(message)
        self.status_label.show()
        self.submit_button.setEnabled(False)
        self.submit_button.setVisible(False)
        self.generate_again_button.setEnabled(False)
        self.start_planning_button.setEnabled(False)
        self.start_planning_button.setVisible(False)
        self.prev_question_button.setEnabled(False)
        self.prev_question_button.setVisible(False)
        self.next_question_button.setEnabled(False)
        self.next_question_button.setVisible(False)

    def clear_question(self):
        """Reset the panel to its empty state."""
        self._set_mode_questions()
        self._clear_questions()
        self.submit_button.setEnabled(False)
        self.generate_again_button.setEnabled(False)
        self.start_planning_button.setEnabled(False)
        self.start_planning_button.setVisible(False)
        self.content_frame.hide()
        self.placeholder_label.show()

    def show_generating_message(self, message: str = "Generating questions..."):
        """Show a waiting message while questions are being generated."""
        self._set_mode_questions()
        self._clear_questions()
        self.placeholder_label.hide()
        self.content_frame.show()
        self.counter_label.setText("")
        self.status_label.setText(message)
        self.status_label.show()
        self.submit_button.setEnabled(False)
        self.generate_again_button.setEnabled(False)
        self.start_planning_button.setEnabled(False)
        self.start_planning_button.setVisible(False)
        self.prev_question_button.setEnabled(False)
        self.prev_question_button.setVisible(False)
        self.next_question_button.setEnabled(False)
        self.next_question_button.setVisible(False)

    def show_activity(self, phase: str = "", action: str = "", agent: str = "",
                      review: str = "", findings: str = ""):
        """Show a compact activity status view in place of questions."""
        self.activity_mode = True
        self.group.setTitle("Live Status")
        self.placeholder_label.hide()
        self.content_frame.hide()
        self.activity_frame.show()

        self._set_activity_line(self.activity_phase_label, "Phase", phase)
        self._set_activity_line(self.activity_action_label, "Now", action)
        self._set_activity_line(self.activity_agent_label, "Agent", agent)
        self._set_activity_line(self.activity_review_label, "Review", review)
        self._set_activity_line(self.activity_findings_label, "Findings", findings)

    def set_readonly(self, readonly: bool):
        """Enable or disable interaction."""
        self._set_questions_readonly(readonly)
        self.submit_button.setEnabled(not readonly and self._all_questions_answered())
        self.generate_again_button.setEnabled(not readonly and self.submitted)
        self.start_planning_button.setEnabled(not readonly and self.start_planning_button.isEnabled())
        self.prev_question_button.setEnabled(not readonly and self.prev_question_button.isEnabled())
        self.next_question_button.setEnabled(not readonly and self.next_question_button.isEnabled())

    def _add_question_entry(self, index: int, question_text: str, options: List[str]):
        entry_box = QGroupBox(f"Question {index}")
        entry_layout = QVBoxLayout(entry_box)
        entry_layout.setSpacing(6)

        question_label = QLabel(question_text)
        question_label.setWordWrap(True)
        question_label.setStyleSheet("font-size: 12px; font-weight: bold; padding: 2px 0;")
        entry_layout.addWidget(question_label)

        options_container = QWidget()
        options_layout = QVBoxLayout(options_container)
        options_layout.setSpacing(4)
        entry_layout.addWidget(options_container)

        option_group = QButtonGroup(self)
        option_group.setExclusive(True)
        option_group.buttonClicked.connect(self._on_answer_changed)

        if options:
            for option in options:
                radio = QRadioButton(str(option))
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
                option_group.addButton(radio)
                options_layout.addWidget(radio)
        else:
            no_options = QLabel("No preset options provided.")
            no_options.setStyleSheet("color: gray; font-size: 12px;")
            options_layout.addWidget(no_options)

        custom_radio = QRadioButton("Custom answer")
        custom_radio.setStyleSheet("""
            QRadioButton {
                font-size: 12px;
                padding: 4px;
                spacing: 8px;
                color: #666666;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
            }
        """)
        option_group.addButton(custom_radio)
        options_layout.addWidget(custom_radio)

        freeform_label = QLabel("Custom answer:")
        freeform_label.setStyleSheet("font-size: 12px;")
        entry_layout.addWidget(freeform_label)

        freeform_edit = QTextEdit()
        freeform_edit.setPlaceholderText("Type your answer here...")
        freeform_edit.setMinimumHeight(60)
        freeform_edit.setEnabled(False)
        freeform_label.setEnabled(False)
        freeform_edit.textChanged.connect(self._on_answer_changed)
        entry_layout.addWidget(freeform_edit)

        custom_radio.toggled.connect(
            partial(self._toggle_custom_input, freeform_edit, freeform_label)
        )

        self.questions_stack.addWidget(entry_box)

        self.question_entries.append({
            "question": question_text,
            "option_group": option_group,
            "custom_radio": custom_radio,
            "freeform_edit": freeform_edit,
            "freeform_label": freeform_label,
        })

    def _toggle_custom_input(self, edit: QTextEdit, label: QLabel, checked: bool):
        edit.setEnabled(checked)
        label.setEnabled(checked)
        if checked:
            edit.setFocus()

    def _clear_questions(self):
        self.question_entries = []
        self.current_index = 0
        self.submitted = False
        while self.questions_stack.count():
            widget = self.questions_stack.widget(0)
            self.questions_stack.removeWidget(widget)
            widget.deleteLater()

    def _set_questions_readonly(self, readonly: bool):
        for entry in self.question_entries:
            group = entry.get("option_group")
            if group:
                for button in group.buttons():
                    button.setEnabled(not readonly)
            freeform_edit = entry.get("freeform_edit")
            custom_radio = entry.get("custom_radio")
            freeform_label = entry.get("freeform_label")
            if isinstance(freeform_edit, QTextEdit):
                if readonly:
                    freeform_edit.setEnabled(False)
                elif isinstance(custom_radio, QRadioButton):
                    freeform_edit.setEnabled(custom_radio.isChecked())
            if isinstance(freeform_label, QLabel):
                if readonly:
                    freeform_label.setEnabled(False)
                elif isinstance(custom_radio, QRadioButton):
                    freeform_label.setEnabled(custom_radio.isChecked())

    def _all_questions_answered(self) -> bool:
        for entry in self.question_entries:
            if not self._get_entry_answer(entry):
                return False
        return bool(self.question_entries)

    def get_unanswered_count(self) -> int:
        """Return the number of unanswered questions in the current batch."""
        return sum(1 for entry in self.question_entries if not self._get_entry_answer(entry))

    def collect_answered_pairs(self) -> List[Dict[str, str]]:
        """Collect only answered question/answer pairs from the current batch."""
        answered = []
        for entry in self.question_entries:
            question_text = str(entry.get("question", "")).strip()
            answer = self._get_entry_answer(entry)
            if question_text and answer:
                answered.append({"question": question_text, "answer": answer})
        return answered

    def _get_entry_answer(self, entry: Dict[str, object]) -> str:
        option_group = entry.get("option_group")
        custom_radio = entry.get("custom_radio")
        freeform_edit = entry.get("freeform_edit")
        if isinstance(option_group, QButtonGroup):
            checked = option_group.checkedButton()
            if checked and checked == custom_radio and isinstance(freeform_edit, QTextEdit):
                return freeform_edit.toPlainText().strip()
            if checked:
                return checked.text().strip()
        return ""

    def _collect_answers(self) -> List[Dict[str, str]]:
        answers = []
        for entry in self.question_entries:
            question_text = str(entry.get("question", "")).strip()
            answer = self._get_entry_answer(entry)
            answers.append({"question": question_text, "answer": answer})
        return answers

    def _on_answer_changed(self):
        all_answered = self._all_questions_answered()
        self.submit_button.setEnabled(all_answered)
        self.generate_again_button.setEnabled(self.submitted)

    def _on_submit(self):
        if not self._all_questions_answered():
            return
        self.answers_submitted.emit(self._collect_answers())

    def _on_generate_again(self):
        self.generate_again_requested.emit()

    def _on_start_planning(self):
        self.start_planning_requested.emit()

    def _on_previous_question(self):
        if self.current_index <= 0:
            return
        self._set_current_question(self.current_index - 1)

    def _on_next_question(self):
        if self.current_index >= len(self.question_entries) - 1:
            return
        self._set_current_question(self.current_index + 1)

    def _set_current_question(self, index: int):
        total = len(self.question_entries)
        if total == 0:
            self.current_index = 0
            self._set_counter_label(0, 0)
            return
        self.current_index = max(0, min(index, total - 1))
        self.questions_stack.setCurrentIndex(self.current_index)
        self._set_counter_label(self.current_index, total)
        self._update_navigation_state()

    def _update_navigation_state(self):
        total = len(self.question_entries)
        if total <= 1:
            self.prev_question_button.setEnabled(False)
            self.next_question_button.setEnabled(False)
            return
        self.prev_question_button.setEnabled(self.current_index > 0)
        self.next_question_button.setEnabled(self.current_index < total - 1)

    def _set_counter_label(self, index: int, total: int):
        if total <= 0:
            self.counter_label.setText("")
            return
        self.counter_label.setText(f"Question {index + 1} of {total}")

    def _set_mode_questions(self):
        """Switch the panel back to question mode."""
        if not self.activity_mode:
            self.group.setTitle("Clarifying Questions")
            return
        self.activity_mode = False
        self.group.setTitle("Clarifying Questions")
        self.activity_frame.hide()

    def _set_activity_line(self, label: QLabel, prefix: str, value: str):
        """Update a single activity line with minimal text."""
        if value:
            label.setText(f"{prefix}: {value}")
            label.show()
        else:
            label.hide()
