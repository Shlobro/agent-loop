"""Keyboard-driven modal dialog for answering generated questions."""

from typing import Dict, List

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)


class QuestionAnswerDialog(QDialog):
    """Shows one question at a time with keyboard-first navigation."""

    _CUSTOM_VALUE = "__custom__"

    def __init__(self, questions: List[Dict[str, object]], parent=None):
        super().__init__(parent)
        self.questions = questions
        self.current_index = 0
        self.answers: List[str] = ["" for _ in questions]
        self._allow_close = False

        self.setWindowTitle("Questions")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.resize(760, 420)

        self._setup_ui()
        self._load_question(0)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.counter_label = QLabel("")
        self.counter_label.setStyleSheet("color: gray;")
        layout.addWidget(self.counter_label)

        self.question_label = QLabel("")
        self.question_label.setWordWrap(True)
        self.question_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.question_label)

        self.hint_label = QLabel(
            "Up/Down: choose answer  Left/Right: previous/next question  Enter: submit and continue"
        )
        self.hint_label.setStyleSheet("color: gray;")
        layout.addWidget(self.hint_label)

        self.options_list = QListWidget()
        self.options_list.currentRowChanged.connect(self._on_option_changed)
        layout.addWidget(self.options_list, stretch=1)

        self.custom_input = QLineEdit()
        self.custom_input.setPlaceholderText("Type custom answer and press Enter")
        self.custom_input.hide()
        self.custom_input.returnPressed.connect(self._submit_current_and_advance)
        layout.addWidget(self.custom_input)

        buttons = QHBoxLayout()
        self.prev_button = QPushButton("Previous")
        self.prev_button.clicked.connect(self._go_previous)
        buttons.addWidget(self.prev_button)

        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self._go_next)
        buttons.addWidget(self.next_button)

        self.enter_button = QPushButton("Submit")
        self.enter_button.clicked.connect(self._submit_current_and_advance)
        buttons.addWidget(self.enter_button)

        layout.addLayout(buttons)

    def keyPressEvent(self, event):
        key = event.key()

        if key in (Qt.Key_Return, Qt.Key_Enter):
            self._submit_current_and_advance()
            event.accept()
            return
        if key == Qt.Key_Escape:
            event.accept()
            return
        if key == Qt.Key_Left:
            self._go_previous()
            event.accept()
            return
        if key == Qt.Key_Right:
            self._go_next()
            event.accept()
            return
        if key == Qt.Key_Up:
            self._move_selection(-1)
            event.accept()
            return
        if key == Qt.Key_Down:
            self._move_selection(1)
            event.accept()
            return

        super().keyPressEvent(event)

    def _move_selection(self, delta: int):
        count = self.options_list.count()
        if count <= 0:
            return
        current = self.options_list.currentRow()
        if current < 0:
            current = 0
        target = max(0, min(count - 1, current + delta))
        self.options_list.setCurrentRow(target)

    def _go_previous(self):
        self._save_current_answer()
        if self.current_index > 0:
            self._load_question(self.current_index - 1)

    def _go_next(self):
        self._save_current_answer()
        if self.current_index < len(self.questions) - 1:
            self._load_question(self.current_index + 1)

    def _submit_current_and_advance(self):
        answer = self._current_answer()
        if not answer:
            return

        self.answers[self.current_index] = answer

        if self.current_index >= len(self.questions) - 1:
            self._allow_close = True
            self.accept()
            return

        self._load_question(self.current_index + 1)

    def _save_current_answer(self):
        answer = self._current_answer()
        if answer:
            self.answers[self.current_index] = answer

    def _current_answer(self) -> str:
        row = self.options_list.currentRow()
        if row < 0:
            return ""

        item = self.options_list.item(row)
        value = item.data(Qt.UserRole)
        if value == self._CUSTOM_VALUE:
            return self.custom_input.text().strip()
        return str(value).strip()

    def _on_option_changed(self, row: int):
        if row < 0:
            self.custom_input.hide()
            return

        item = self.options_list.item(row)
        value = item.data(Qt.UserRole)
        is_custom = value == self._CUSTOM_VALUE
        self.custom_input.setVisible(is_custom)
        if is_custom:
            self.custom_input.setFocus()
            self.custom_input.selectAll()
        else:
            self.options_list.setFocus()

    def _load_question(self, index: int):
        total = len(self.questions)
        if total == 0:
            return

        self.current_index = max(0, min(index, total - 1))
        question = self.questions[self.current_index]

        question_text = str(question.get("question", "")).strip()
        options = question.get("options") or []

        self.counter_label.setText(f"Question {self.current_index + 1} of {total}")
        self.question_label.setText(question_text)

        self.options_list.clear()
        normalized = [str(option).strip() for option in options if str(option).strip()]

        for option in normalized:
            item = QListWidgetItem(option)
            item.setData(Qt.UserRole, option)
            self.options_list.addItem(item)

        custom_item = QListWidgetItem("Custom answer")
        custom_item.setData(Qt.UserRole, self._CUSTOM_VALUE)
        self.options_list.addItem(custom_item)

        saved = self.answers[self.current_index].strip()
        selected_row = 0
        custom_text = ""
        if saved:
            matched = False
            for row in range(self.options_list.count()):
                value = str(self.options_list.item(row).data(Qt.UserRole))
                if value == saved:
                    selected_row = row
                    matched = True
                    break
            if not matched:
                selected_row = self.options_list.count() - 1
                custom_text = saved

        self.options_list.setCurrentRow(selected_row)
        self.custom_input.setText(custom_text)

        self.prev_button.setEnabled(self.current_index > 0)
        self.next_button.setEnabled(self.current_index < total - 1)
        self.enter_button.setText("Submit & Close" if self.current_index == total - 1 else "Submit & Next")
        self.options_list.setFocus()

    def get_qa_pairs(self) -> List[Dict[str, str]]:
        pairs: List[Dict[str, str]] = []
        for index, question in enumerate(self.questions):
            question_text = str(question.get("question", "")).strip()
            answer = self.answers[index].strip()
            if question_text and answer:
                pairs.append({"question": question_text, "answer": answer})
        return pairs

    def reject(self):
        """Disallow closing the dialog until the final answer is submitted."""
        if self._allow_close:
            super().reject()

    def closeEvent(self, event: QCloseEvent):
        """Block window-close actions until final submit."""
        if self._allow_close:
            super().closeEvent(event)
            return
        event.ignore()
