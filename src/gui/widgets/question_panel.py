"""Hidden bridge widget for question flow signals and modal answer collection."""

from typing import Dict, List

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QWidget

from ..dialogs.question_answer_dialog import QuestionAnswerDialog


class QuestionPanel(QWidget):
    """Keeps question flow signal wiring while using a modal answer window."""

    answers_submitted = Signal(list)  # [{"question": str, "answer": str}]
    generate_again_requested = Signal()
    start_planning_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._readonly = False
        self._submitted_pairs: List[Dict[str, str]] = []
        self.hide()

    def show_questions(self, questions: List[Dict[str, object]]):
        """Open keyboard-driven modal question window and emit submitted answers."""
        dialog = QuestionAnswerDialog(questions, parent=self.window())
        if dialog.exec() != QuestionAnswerDialog.Accepted:
            return

        self._submitted_pairs = dialog.get_qa_pairs()
        if self._submitted_pairs:
            self.answers_submitted.emit(list(self._submitted_pairs))

    def show_answers_saved(self):
        """Auto-advance to planning after answers are processed."""
        QTimer.singleShot(0, self.start_planning_requested.emit)

    def show_updating_description(self, message: str = "Updating project description..."):
        _ = message

    def clear_question(self):
        self._submitted_pairs = []

    def show_generating_message(self, message: str = "Generating questions..."):
        _ = message

    def show_activity(self, phase: str = "", action: str = "", agent: str = "",
                      review: str = "", findings: str = ""):
        _ = (phase, action, agent, review, findings)

    def set_readonly(self, readonly: bool):
        self._readonly = readonly

    def get_unanswered_count(self) -> int:
        return 0

    def collect_answered_pairs(self) -> List[Dict[str, str]]:
        return list(self._submitted_pairs)
