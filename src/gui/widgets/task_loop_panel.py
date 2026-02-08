"""Panel that highlights live main-loop task activity."""

from typing import List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QLabel, QTextBrowser
)


class TaskLoopPanel(QWidget):
    """Displays current loop action and task completion breakdown."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Agent Loop Status")
        group_layout = QVBoxLayout(group)

        self.current_action_label = QLabel("Current Action: Waiting")
        self.current_action_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        group_layout.addWidget(self.current_action_label)

        self.summary_label = QLabel("Completed: 0 | Incomplete: 0 | Total: 0")
        self.summary_label.setProperty("role", "muted")
        self.summary_label.setStyleSheet("font-size: 15px;")
        group_layout.addWidget(self.summary_label)

        completed_title = QLabel("Completed Tasks")
        completed_title.setStyleSheet("font-size: 15px; font-weight: 600;")
        group_layout.addWidget(completed_title)

        self.completed_view = QTextBrowser()
        self.completed_view.setOpenExternalLinks(True)
        self.completed_view.setMinimumHeight(120)
        group_layout.addWidget(self.completed_view)

        incomplete_title = QLabel("Incomplete Tasks")
        incomplete_title.setStyleSheet("font-size: 15px; font-weight: 600;")
        group_layout.addWidget(incomplete_title)

        self.incomplete_view = QTextBrowser()
        self.incomplete_view.setOpenExternalLinks(True)
        self.incomplete_view.setMinimumHeight(120)
        group_layout.addWidget(self.incomplete_view)

        layout.addWidget(group)

    def set_current_action(self, action: str):
        """Set current in-loop action line."""
        value = action.strip() if action else "Waiting"
        self.current_action_label.setText(f"Current Action: {value}")

    def set_tasks(self, completed_tasks: List[str], incomplete_tasks: List[str]):
        """Render completed and incomplete task lists with counts."""
        total = len(completed_tasks) + len(incomplete_tasks)
        self.summary_label.setText(
            f"Completed: {len(completed_tasks)} | Incomplete: {len(incomplete_tasks)} | Total: {total}"
        )
        self.completed_view.setMarkdown(self._tasks_to_markdown(completed_tasks, "No completed tasks yet."))
        self.incomplete_view.setMarkdown(
            self._tasks_to_markdown(incomplete_tasks, "No incomplete tasks remaining.")
        )

    def clear(self):
        """Reset panel to initial state."""
        self.set_current_action("Waiting")
        self.set_tasks([], [])

    @staticmethod
    def _tasks_to_markdown(tasks: List[str], empty_text: str) -> str:
        if not tasks:
            return f"_{empty_text}_"
        return "\n".join(f"- {task}" for task in tasks)
