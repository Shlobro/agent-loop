"""Hidden bridge widget for question flow signals and modal answer collection."""

from typing import Dict, List, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from ..dialogs.question_answer_dialog import QuestionAnswerDialog
from ..dialogs.question_flow_decision_dialog import QuestionFlowDecisionDialog


class QuestionPanel(QWidget):
    """Keeps question flow signal wiring while using a modal answer window."""

    answers_submitted = Signal(list)  # [{"question": str, "answer": str}]
    generate_again_requested = Signal()
    start_planning_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._readonly = False
        self._submitted_pairs: List[Dict[str, str]] = []
        self._decision_dialog: Optional[QuestionFlowDecisionDialog] = None
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
        """Prompt user to either ask more questions or start the main loop."""
        if self._decision_dialog is None:
            self._decision_dialog = QuestionFlowDecisionDialog(parent=self.window())
            self._decision_dialog.ask_more_requested.connect(self.generate_again_requested.emit)
            self._decision_dialog.start_main_loop_requested.connect(self.start_planning_requested.emit)
            self._decision_dialog.finished.connect(self._on_decision_dialog_finished)

        self._decision_dialog.show()
        self._decision_dialog.raise_()
        self._decision_dialog.activateWindow()

    def show_updating_description(self, message: str = "Updating project description..."):
        _ = message

    def clear_question(self):
        self._submitted_pairs = []
        if self._decision_dialog is not None:
            self._decision_dialog.deleteLater()
            self._decision_dialog = None

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

    def _on_decision_dialog_finished(self, _result: int):
        self._decision_dialog = None
