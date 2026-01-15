"""Status panel showing current phase, iteration, and progress."""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QProgressBar, QFrame
)
from PySide6.QtCore import Slot, Qt


class StatusPanel(QWidget):
    """
    Displays current execution status including:
    - Current phase (Questions, Planning, Executing, Reviewing, Git)
    - Current iteration number
    - Overall progress bar
    - Sub-status for detailed info
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        # Main frame with border
        self.setStyleSheet("""
            StatusPanel {
                background-color: palette(base);
                border: 1px solid palette(mid);
                border-radius: 4px;
                padding: 4px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        # Phase indicator
        self.phase_label = QLabel("Phase: Idle")
        self.phase_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(self.phase_label)

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep1)

        # Iteration indicator
        self.iteration_label = QLabel("Iteration: -")
        self.iteration_label.setMinimumWidth(100)
        layout.addWidget(self.iteration_label)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep2)

        # Sub-status (detailed info)
        self.sub_status_label = QLabel("")
        self.sub_status_label.setStyleSheet("color: gray;")
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

    @Slot(str)
    def set_phase(self, phase: str):
        """Set the current phase display."""
        self.phase_label.setText(f"Phase: {phase}")

        # Color code by phase
        colors = {
            "Idle": "gray",
            "Generating Questions": "#9370DB",
            "Awaiting Answers": "#FFA500",
            "Planning Tasks": "#00CED1",
            "Executing Tasks": "#32CD32",
            "Code Review": "#FF69B4",
            "Git Operations": "#4169E1",
            "Completed": "#00FF00",
            "Paused": "#FFD700",
            "Error": "#FF4444",
            "Cancelled": "#FF6347",
        }
        color = colors.get(phase, "white")
        self.phase_label.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {color};")

    @Slot(int, int)
    def set_iteration(self, current: int, total: int):
        """Set iteration display and update progress bar."""
        if total > 0:
            self.iteration_label.setText(f"Iteration: {current}/{total}")
            progress = int((current / total) * 100)
            self.progress_bar.setValue(progress)
        else:
            self.iteration_label.setText("Iteration: -")
            self.progress_bar.setValue(0)

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
        self.phase_label.setStyleSheet("font-weight: bold; font-size: 12px; color: gray;")
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
            self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: gray; }")
