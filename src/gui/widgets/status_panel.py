"""Status panel showing current phase, iteration, and task-based progress."""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QProgressBar, QFrame, QPushButton
)
from PySide6.QtCore import Slot, Qt, Signal


class StatusPanel(QWidget):
    """
    Displays current execution status including:
    - Current phase (Questions, Planning, Executing, Reviewing, Git)
    - Current iteration number
    - Overall progress bar
    - Sub-status for detailed info
    - Resume button for incomplete tasks
    """

    resume_incomplete_tasks = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        # Phase indicator
        self.phase_label = QLabel("Phase: Idle")
        self.phase_label.setStyleSheet("font-size: 17px; font-weight: 700;")
        layout.addWidget(self.phase_label)

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep1)

        # Iteration indicator
        self.iteration_label = QLabel("Iteration: -")
        self.iteration_label.setMinimumWidth(100)
        self.iteration_label.setStyleSheet("font-size: 15px;")
        layout.addWidget(self.iteration_label)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep2)

        # Sub-status (detailed info)
        self.sub_status_label = QLabel("")
        self.sub_status_label.setProperty("role", "muted")
        self.sub_status_label.setStyleSheet("font-size: 15px;")
        layout.addWidget(self.sub_status_label)

        layout.addStretch()

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setMinimumWidth(150)
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        # Resume button for incomplete tasks
        self.resume_button = QPushButton("Resume Tasks")
        self.resume_button.setToolTip("Resume incomplete tasks from tasks.md")
        self.resume_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #2f8fd1, stop:1 #266da9);
                color: white;
                border: 1px solid #57a7dc;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 600;
                font-size: 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #3b9ce0, stop:1 #2d78b8);
                border-color: #6eb5e3;
            }
            QPushButton:pressed {
                background: #245f95;
            }
            QPushButton:disabled {
                background: #1d2a36;
                border-color: #2a3e4f;
                color: #7f9bb4;
            }
        """)
        self.resume_button.clicked.connect(self.resume_incomplete_tasks.emit)
        self.resume_button.hide()
        layout.addWidget(self.resume_button)

    @Slot(str)
    def set_phase(self, phase: str):
        """Set the current phase display."""
        self.phase_label.setText(f"Phase: {phase}")

        # Color code by phase
        colors = {
            "Idle": "#8e99a6",
            "Generating Questions": "#76b7e5",
            "Awaiting Answers": "#e6b86e",
            "Planning Tasks": "#69d0cb",
            "Executing Tasks": "#7ed082",
            "Code Review": "#8cb4ff",
            "Git Operations": "#9aa7ff",
            "Completed": "#8fd9a8",
            "Paused": "#dbcd7a",
            "Error": "#ef7d7d",
            "Cancelled": "#e8937d",
        }
        color = colors.get(phase, "white")
        self.phase_label.setStyleSheet(f"font-size: 17px; font-weight: 700; color: {color};")

    @Slot(int, int)
    def set_iteration(self, current: int, total: int):
        """Set iteration display."""
        if total > 0:
            self.iteration_label.setText(f"Iteration: {current}/{total}")
        else:
            self.iteration_label.setText("Iteration: -")

    @Slot(int, int)
    def set_task_progress(self, completed: int, total: int):
        """Set progress bar from task completion counts."""
        if total <= 0:
            self.progress_bar.setValue(0)
            return
        progress = int((completed / total) * 100)
        self.progress_bar.setValue(max(0, min(100, progress)))

    @Slot(str)
    def set_sub_status(self, status: str):
        """Set detailed sub-status text."""
        self.sub_status_label.setText(status)

    @Slot(int)
    def set_progress(self, value: int):
        """Directly set progress bar value (0-100)."""
        self.progress_bar.setValue(max(0, min(100, value)))

    def reset(self):
        """Reset all status indicators."""
        self.phase_label.setText("Phase: Idle")
        self.phase_label.setStyleSheet("font-size: 17px; font-weight: 700; color: #8e99a6;")
        self.iteration_label.setText("Iteration: -")
        self.sub_status_label.setText("")
        self.progress_bar.setValue(0)

    def set_running(self, running: bool):
        """
        Update visual state for running/stopped.
        """
        if running:
            self.progress_bar.setStyleSheet("")
        else:
            self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #5f6872; }")

    @Slot(bool)
    def set_resume_button_visible(self, visible: bool):
        """Show or hide the resume tasks button."""
        self.resume_button.setVisible(visible)
