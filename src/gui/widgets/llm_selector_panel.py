"""Panel for selecting LLM providers for each stage."""

from PySide6.QtWidgets import (
    QWidget, QGridLayout, QLabel, QComboBox, QGroupBox, QVBoxLayout
)
from PySide6.QtCore import Signal
from typing import Dict
from dataclasses import dataclass


@dataclass
class LLMConfig:
    """Configuration for LLM providers per stage."""
    question_gen: str
    task_planning: str
    coder: str
    reviewer: str
    fixer: str
    git_ops: str


class LLMSelectorPanel(QWidget):
    """
    Panel with dropdown selectors for each LLM stage.
    Available LLMs: Claude, Gemini, Codex
    """

    config_changed = Signal()

    LLM_OPTIONS = ["gemini", "claude", "codex"]
    LLM_DISPLAY_NAMES = {
        "claude": "Claude",
        "gemini": "Gemini",
        "codex": "Codex"
    }

    STAGES = [
        ("question_gen", "Question Generation"),
        ("task_planning", "Task Planning"),
        ("coder", "Coder (Main Loop)"),
        ("reviewer", "Reviewer"),
        ("fixer", "Fixer"),
        ("git_ops", "Git Operations"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.combos: Dict[str, QComboBox] = {}
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("LLM Selection")
        grid = QGridLayout(group)

        for row, (key, label_text) in enumerate(self.STAGES):
            # Label
            label = QLabel(f"{label_text}:")
            grid.addWidget(label, row, 0)

            # Combo box
            combo = QComboBox()
            for llm_id in self.LLM_OPTIONS:
                combo.addItem(self.LLM_DISPLAY_NAMES[llm_id], llm_id)

            # Set default to Gemini (first in LLM_OPTIONS)
            combo.setCurrentIndex(0)
            combo.currentIndexChanged.connect(self._on_config_changed)

            grid.addWidget(combo, row, 1)
            self.combos[key] = combo

        layout.addWidget(group)

    def _on_config_changed(self):
        """Emit signal when any selection changes."""
        self.config_changed.emit()

    def get_config(self) -> LLMConfig:
        """Get current LLM configuration."""
        return LLMConfig(
            question_gen=self.combos["question_gen"].currentData(),
            task_planning=self.combos["task_planning"].currentData(),
            coder=self.combos["coder"].currentData(),
            reviewer=self.combos["reviewer"].currentData(),
            fixer=self.combos["fixer"].currentData(),
            git_ops=self.combos["git_ops"].currentData(),
        )

    def get_config_dict(self) -> Dict[str, str]:
        """Get configuration as dictionary."""
        config = self.get_config()
        return {
            "question_gen": config.question_gen,
            "task_planning": config.task_planning,
            "coder": config.coder,
            "reviewer": config.reviewer,
            "fixer": config.fixer,
            "git_ops": config.git_ops,
        }

    def set_config(self, config: Dict[str, str]):
        """Set LLM configuration from dictionary."""
        for key, value in config.items():
            if key in self.combos:
                combo = self.combos[key]
                # Find index by data
                for i in range(combo.count()):
                    if combo.itemData(i) == value:
                        combo.setCurrentIndex(i)
                        break

    def set_all_to(self, llm_name: str):
        """Set all stages to use the same LLM."""
        for combo in self.combos.values():
            for i in range(combo.count()):
                if combo.itemData(i) == llm_name:
                    combo.setCurrentIndex(i)
                    break

    def set_enabled(self, enabled: bool):
        """Enable or disable all combos."""
        for combo in self.combos.values():
            combo.setEnabled(enabled)
