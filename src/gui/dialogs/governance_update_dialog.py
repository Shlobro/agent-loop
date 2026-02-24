"""Dialog shown when existing governance files don't match the current recommended content."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget
)
from PySide6.QtCore import Qt


class GovernanceUpdateDialog(QDialog):
    """
    Modal dialog shown when CLAUDE.md / AGENTS.md / GEMINI.md exist in the
    selected project folder but their contents differ from the current
    recommended AgentHarness template.

    The user can choose to:
    - Append: add the recommended content at the end of each stale file
    - Replace: overwrite each stale file with the recommended content
    - Skip: leave the files as-is

    After exec(), check .choice — one of "append", "replace", or "skip".
    """

    APPEND = "append"
    REPLACE = "replace"
    SKIP = "skip"

    def __init__(self, stale_files: list[str], parent=None):
        super().__init__(parent)
        self.stale_files = stale_files
        self.choice = self.SKIP
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Governance Files Out of Date")
        self.setMinimumWidth(480)
        self.setWindowModality(Qt.ApplicationModal)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header
        header = QLabel("Agent instruction files need updating")
        header.setProperty("role", "hero_subtitle")
        layout.addWidget(header)

        # Explanation
        body = QLabel(
            "The following files already exist in this project folder but do not "
            "match the latest recommended settings for AgentHarness. Keeping them "
            "up to date ensures agents receive the correct instructions."
        )
        body.setWordWrap(True)
        layout.addWidget(body)

        # File list
        file_list = QListWidget()
        file_list.setFixedHeight(80)
        for name in self.stale_files:
            file_list.addItem(name)
        layout.addWidget(file_list)

        # Options explanation
        options_label = QLabel(
            "<b>Append</b> — add the recommended instructions at the end of each file "
            "(safe if you have custom rules you want to keep).<br>"
            "<b>Replace</b> — overwrite each file with the recommended content only."
        )
        options_label.setWordWrap(True)
        options_label.setTextFormat(Qt.RichText)
        layout.addWidget(options_label)

        # Buttons
        button_layout = QHBoxLayout()

        skip_btn = QPushButton("Skip")
        skip_btn.clicked.connect(self._on_skip)
        button_layout.addWidget(skip_btn)

        button_layout.addStretch()

        append_btn = QPushButton("Append")
        append_btn.clicked.connect(self._on_append)
        button_layout.addWidget(append_btn)

        replace_btn = QPushButton("Replace")
        replace_btn.setProperty("variant", "primary")
        replace_btn.clicked.connect(self._on_replace)
        replace_btn.setDefault(True)
        button_layout.addWidget(replace_btn)

        layout.addLayout(button_layout)

    def _on_append(self):
        self.choice = self.APPEND
        self.accept()

    def _on_replace(self):
        self.choice = self.REPLACE
        self.accept()

    def _on_skip(self):
        self.choice = self.SKIP
        self.reject()
