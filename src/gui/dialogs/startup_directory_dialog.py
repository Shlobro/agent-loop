"""Startup dialog that requires selecting a working directory."""

from pathlib import Path
from typing import List

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class StartupDirectoryDialog(QDialog):
    """Require a working directory selection before app usage."""

    def __init__(self, recent_directories: List[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Working Directory")
        self.setModal(True)
        self.setMinimumWidth(700)
        self._selected_directory = ""
        self._recent_directories = recent_directories
        self._setup_ui()
        self._load_recent_directories()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        message = QLabel(
            "Choose a working directory to continue.\n"
            "Project settings are stored under .agentharness in that directory."
        )
        message.setWordWrap(True)
        layout.addWidget(message)

        self.recent_list = QListWidget()
        self.recent_list.itemDoubleClicked.connect(self._on_recent_double_clicked)
        self.recent_list.itemSelectionChanged.connect(self._on_recent_selection_changed)
        layout.addWidget(self.recent_list)

        actions_layout = QHBoxLayout()
        self.use_selected_button = QPushButton("Use Selected")
        self.use_selected_button.setEnabled(False)
        self.use_selected_button.clicked.connect(self._accept_selected_recent)
        actions_layout.addWidget(self.use_selected_button)

        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse_for_directory)
        actions_layout.addWidget(browse_button)
        actions_layout.addStretch()
        layout.addLayout(actions_layout)

        self.selected_label = QLabel("Selected: none")
        self.selected_label.setWordWrap(True)
        layout.addWidget(self.selected_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_recent_directories(self):
        for path in self._recent_directories:
            if not path:
                continue
            path_obj = Path(path)
            if not path_obj.exists() or not path_obj.is_dir():
                continue
            self.recent_list.addItem(QListWidgetItem(path))

    def _on_recent_selection_changed(self):
        item = self.recent_list.currentItem()
        enabled = item is not None
        self.use_selected_button.setEnabled(enabled)
        if enabled:
            self._selected_directory = item.text().strip()
            self.selected_label.setText(f"Selected: {self._selected_directory}")
        else:
            self.selected_label.setText("Selected: none")

    def _on_recent_double_clicked(self, item: QListWidgetItem):
        self._selected_directory = item.text().strip()
        self._try_accept()

    def _accept_selected_recent(self):
        item = self.recent_list.currentItem()
        if not item:
            return
        self._selected_directory = item.text().strip()
        self._try_accept()

    def _browse_for_directory(self):
        start_dir = (
            self._selected_directory
            if self._selected_directory and Path(self._selected_directory).exists()
            else str(Path.home())
        )
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Working Directory",
            start_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if not directory:
            return
        self._selected_directory = directory
        self.selected_label.setText(f"Selected: {directory}")
        self._try_accept()

    def _try_accept(self):
        path_obj = Path(self._selected_directory)
        if not self._selected_directory or not path_obj.exists() or not path_obj.is_dir():
            QMessageBox.warning(
                self,
                "Invalid Directory",
                "Please choose a valid working directory.",
            )
            return
        self.accept()

    def get_selected_directory(self) -> str:
        """Return selected working directory."""
        return self._selected_directory
