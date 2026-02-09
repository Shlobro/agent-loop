"""Panel for user project description input."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit, QTextBrowser,
    QHBoxLayout, QPushButton, QStackedWidget
)
from PySide6.QtCore import Signal
from typing import List


class DescriptionPanel(QWidget):
    """
    Panel for user to enter project description.
    Supports three view modes: Edit, Preview, and Task List.
    Emits signal when description changes.
    """

    description_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.prompt_label = QLabel("Product Description")
        self.prompt_label.setProperty("role", "hero")
        self.prompt_label.setWordWrap(True)
        layout.addWidget(self.prompt_label)

        self.text_edit = QTextEdit()
        self.text_edit.setStyleSheet("font-size: 17px;")
        self.text_edit.setMinimumHeight(300)
        self.text_edit.textChanged.connect(self._on_text_changed)

        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(True)
        self.preview.setMinimumHeight(300)

        # Task List view
        self.task_list_widget = QWidget()
        task_list_layout = QVBoxLayout(self.task_list_widget)
        task_list_layout.setContentsMargins(8, 8, 8, 8)

        self.current_action_label = QLabel("Current Action: Waiting")
        self.current_action_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        task_list_layout.addWidget(self.current_action_label)

        self.task_summary_label = QLabel("Completed: 0 | Incomplete: 0 | Total: 0")
        self.task_summary_label.setProperty("role", "muted")
        self.task_summary_label.setStyleSheet("font-size: 15px;")
        task_list_layout.addWidget(self.task_summary_label)

        completed_title = QLabel("Completed Tasks")
        completed_title.setStyleSheet("font-size: 15px; font-weight: 600; margin-top: 12px;")
        task_list_layout.addWidget(completed_title)

        self.completed_tasks_view = QTextBrowser()
        self.completed_tasks_view.setOpenExternalLinks(True)
        self.completed_tasks_view.setMinimumHeight(120)
        task_list_layout.addWidget(self.completed_tasks_view)

        incomplete_title = QLabel("Incomplete Tasks")
        incomplete_title.setStyleSheet("font-size: 15px; font-weight: 600; margin-top: 12px;")
        task_list_layout.addWidget(incomplete_title)

        self.incomplete_tasks_view = QTextBrowser()
        self.incomplete_tasks_view.setOpenExternalLinks(True)
        self.incomplete_tasks_view.setMinimumHeight(120)
        task_list_layout.addWidget(self.incomplete_tasks_view)

        self.mode_row_widget = QWidget()
        mode_row = QHBoxLayout(self.mode_row_widget)
        mode_row.setContentsMargins(0, 0, 0, 0)
        mode_label = QLabel("View")
        mode_label.setProperty("role", "muted")
        mode_row.addWidget(mode_label)

        self.edit_mode_button = QPushButton("Edit")
        self.edit_mode_button.setCheckable(True)
        self.edit_mode_button.clicked.connect(self._enter_edit_mode)
        mode_row.addWidget(self.edit_mode_button)

        self.preview_mode_button = QPushButton("Preview")
        self.preview_mode_button.setCheckable(True)
        self.preview_mode_button.clicked.connect(self._enter_preview_mode)
        mode_row.addWidget(self.preview_mode_button)

        self.task_list_mode_button = QPushButton("Task List")
        self.task_list_mode_button.setCheckable(True)
        self.task_list_mode_button.clicked.connect(self._enter_task_list_mode)
        mode_row.addWidget(self.task_list_mode_button)

        mode_row.addStretch(1)
        layout.addWidget(self.mode_row_widget)

        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(self.text_edit)
        self.content_stack.addWidget(self.preview)
        self.content_stack.addWidget(self.task_list_widget)
        layout.addWidget(self.content_stack)
        self._refresh_preview()
        self._set_mode("edit")
        self.set_preview_controls_visible(False)

    def _on_text_changed(self):
        """Emit signal when text changes."""
        self._refresh_preview()
        self.description_changed.emit(self.get_description())

    def get_description(self) -> str:
        """Get the current description text."""
        return self.text_edit.toPlainText().strip()

    def set_description(self, text: str):
        """Set the description text."""
        self.text_edit.setPlainText(text)
        self._refresh_preview()

    def set_readonly(self, readonly: bool):
        """Enable or disable editing."""
        self.text_edit.setReadOnly(readonly)
        self.edit_mode_button.setEnabled(not readonly)
        if readonly and self.content_stack.currentWidget() is self.text_edit:
            self._set_mode("preview")
        elif not readonly and self.content_stack.currentWidget() is self.text_edit:
            self._set_mode("edit")

    def set_preview_controls_visible(self, visible: bool):
        """Show or hide explicit Edit/Preview/Task List controls."""
        self.mode_row_widget.setVisible(bool(visible))

    def set_preview_mode(self, enabled: bool):
        """Switch between edit and markdown preview mode."""
        if enabled:
            self._set_mode("preview")
        else:
            self._set_mode("edit")

    def is_preview_mode(self) -> bool:
        """Return True when markdown preview mode is active."""
        return self.content_stack.currentWidget() is self.preview

    def is_task_list_mode(self) -> bool:
        """Return True when task list mode is active."""
        return self.content_stack.currentWidget() is self.task_list_widget

    def append_qa_pairs(self, qa_pairs: list):
        """Append answered clarifying questions to the description text."""
        if not qa_pairs:
            return
        current = self.text_edit.toPlainText().rstrip()
        lines = [current] if current else []
        if current:
            lines.append("")
        lines.append("Clarifying Questions and Answers:")
        for i, qa in enumerate(qa_pairs, 1):
            question = str(qa.get("question", "")).strip()
            answer = str(qa.get("answer", "")).strip()
            if question and answer:
                lines.append(f"Q{i}: {question}")
                lines.append(f"A{i}: {answer}")
        self.set_description("\n".join(lines).rstrip())

    def clear(self):
        """Clear the description."""
        self.text_edit.clear()
        self._refresh_preview()

    def is_empty(self) -> bool:
        """Check if description is empty."""
        return len(self.get_description()) == 0

    def _refresh_preview(self):
        """Render current description as Markdown preview."""
        markdown = self.get_description()
        if markdown:
            self.preview.setMarkdown(markdown)
            return
        self.preview.setMarkdown(
            "_Markdown preview appears here once the project description has content._"
        )

    def set_tasks(self, completed_tasks: List[str], incomplete_tasks: List[str]):
        """Update the task list view with completed and incomplete tasks."""
        total = len(completed_tasks) + len(incomplete_tasks)
        self.task_summary_label.setText(
            f"Completed: {len(completed_tasks)} | Incomplete: {len(incomplete_tasks)} | Total: {total}"
        )
        self.completed_tasks_view.setMarkdown(
            self._tasks_to_markdown(completed_tasks, "No completed tasks yet.")
        )
        self.incomplete_tasks_view.setMarkdown(
            self._tasks_to_markdown(incomplete_tasks, "No incomplete tasks remaining.")
        )

    def set_current_action(self, action: str):
        """Set the current action label in task list view."""
        value = action.strip() if action else "Waiting"
        self.current_action_label.setText(f"Current Action: {value}")

    @staticmethod
    def _tasks_to_markdown(tasks: List[str], empty_text: str) -> str:
        """Convert task list to markdown format."""
        if not tasks:
            return f"_{empty_text}_"
        return "\n".join(f"- {task}" for task in tasks)

    def _set_mode(self, mode: str):
        """Set the current view mode: 'edit', 'preview', or 'task_list'."""
        if mode == "edit":
            self.content_stack.setCurrentWidget(self.text_edit)
            self.edit_mode_button.setChecked(True)
            self.preview_mode_button.setChecked(False)
            self.task_list_mode_button.setChecked(False)
        elif mode == "preview":
            self.content_stack.setCurrentWidget(self.preview)
            self.edit_mode_button.setChecked(False)
            self.preview_mode_button.setChecked(True)
            self.task_list_mode_button.setChecked(False)
        elif mode == "task_list":
            self.content_stack.setCurrentWidget(self.task_list_widget)
            self.edit_mode_button.setChecked(False)
            self.preview_mode_button.setChecked(False)
            self.task_list_mode_button.setChecked(True)

    def _enter_edit_mode(self):
        self._set_mode("edit")

    def _enter_preview_mode(self):
        self._set_mode("preview")

    def _enter_task_list_mode(self):
        self._set_mode("task_list")
