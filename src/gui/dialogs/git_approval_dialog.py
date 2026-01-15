"""Dialog for git push approval."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QCheckBox
)
from PySide6.QtCore import Qt


class GitApprovalDialog(QDialog):
    """
    Modal dialog asking user to approve git push.
    Shows commit info and allows user to approve or skip.
    """

    def __init__(self, parent=None, commit_message: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Git Push Approval")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.commit_message = commit_message
        self.remember_choice = False
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Info label
        info_label = QLabel(
            "Changes have been committed. Do you want to push to the remote repository?"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Commit message display
        if self.commit_message:
            commit_label = QLabel(f"<b>Commit:</b> {self.commit_message}")
            commit_label.setWordWrap(True)
            commit_label.setStyleSheet("padding: 10px; background-color: palette(base); border-radius: 4px;")
            layout.addWidget(commit_label)

        # Remember choice checkbox
        self.remember_checkbox = QCheckBox("Remember this choice for this session")
        layout.addWidget(self.remember_checkbox)

        # Buttons
        button_box = QDialogButtonBox()

        self.push_button = button_box.addButton("Push", QDialogButtonBox.AcceptRole)
        self.push_button.setDefault(True)

        self.skip_button = button_box.addButton("Skip Push", QDialogButtonBox.RejectRole)

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(button_box)

    def accept(self):
        """Handle push approval."""
        self.remember_choice = self.remember_checkbox.isChecked()
        super().accept()

    def reject(self):
        """Handle skip."""
        self.remember_choice = self.remember_checkbox.isChecked()
        super().reject()

    def should_push(self) -> bool:
        """Return True if user approved push."""
        return self.result() == QDialog.Accepted

    def should_remember(self) -> bool:
        """Return True if user wants to remember choice."""
        return self.remember_choice

    @staticmethod
    def get_approval(parent=None, commit_message: str = "") -> tuple:
        """
        Static method to show dialog and get result.

        Returns:
            (should_push: bool, remember: bool)
        """
        dialog = GitApprovalDialog(parent, commit_message)
        dialog.exec()
        return dialog.should_push(), dialog.should_remember()
