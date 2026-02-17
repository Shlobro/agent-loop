"""Panel for selecting LLM providers and models for each stage."""

from PySide6.QtWidgets import (
    QWidget, QGridLayout, QLabel, QComboBox, QGroupBox, QVBoxLayout
)
from PySide6.QtCore import Signal
from typing import Dict, Optional
from dataclasses import dataclass

from ...llm.base_provider import LLMProviderRegistry


@dataclass
class StageConfig:
    """Configuration for a single stage."""
    provider: str
    model: str


@dataclass
class LLMConfig:
    """Configuration for LLM providers per stage."""
    question_gen: str
    description_molding: str
    research: str
    task_planning: str
    coder: str
    reviewer: str
    fixer: str
    unit_test_prep: str
    git_ops: str
    client_message_handler: str
    # Model selections for each stage
    question_gen_model: str = ""
    description_molding_model: str = ""
    research_model: str = ""
    task_planning_model: str = ""
    coder_model: str = ""
    reviewer_model: str = ""
    fixer_model: str = ""
    unit_test_prep_model: str = ""
    git_ops_model: str = ""
    client_message_handler_model: str = ""


class LLMSelectorPanel(QWidget):
    """
    Panel with dropdown selectors for each LLM stage.
    Supports both provider and model selection per stage.
    """

    config_changed = Signal()

    STAGES = [
        ("question_gen", "Question Generation"),
        ("description_molding", "Description Molding"),
        ("task_planning", "Task Planning"),
        ("research", "Research (after task planning)"),
        ("coder", "Coder (Main Loop)"),
        ("unit_test_prep", "Unit Test Prep (runs before review)"),
        ("reviewer", "Reviewer"),
        ("fixer", "Fixer"),
        ("git_ops", "Git Operations"),
        ("client_message_handler", "Client Message Handler"),
    ]
    DEFAULT_STAGE_CONFIG = {
        "question_gen": ("gemini", "gemini-3-pro-preview"),
        "description_molding": ("gemini", "gemini-3-pro-preview"),
        "research": ("gemini", "gemini-3-pro-preview"),
        "task_planning": ("claude", "claude-opus-4-6"),
        "coder": ("claude", "claude-opus-4-6"),
        "reviewer": ("codex", "gpt-5.3-codex"),
        "fixer": ("codex", "gpt-5.3-codex"),
        "unit_test_prep": ("gemini", "gemini-3-pro-preview"),
        "git_ops": ("gemini", "gemini-3-pro-preview"),
        "client_message_handler": ("gemini", "gemini-3-pro-preview"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.provider_combos: Dict[str, QComboBox] = {}
        self.model_combos: Dict[str, QComboBox] = {}
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("LLM Selection")
        grid = QGridLayout(group)

        # Headers
        grid.addWidget(QLabel("Stage"), 0, 0)
        grid.addWidget(QLabel("Provider"), 0, 1)
        grid.addWidget(QLabel("Model"), 0, 2)

        # Get providers from registry
        providers = LLMProviderRegistry.get_all()
        provider_names = list(providers.keys())

        for row, (key, label_text) in enumerate(self.STAGES, start=1):
            # Stage label
            label = QLabel(f"{label_text}:")
            grid.addWidget(label, row, 0)

            # Provider combo box
            provider_combo = QComboBox()
            for provider_name in provider_names:
                provider = providers[provider_name]
                provider_combo.addItem(provider.display_name, provider_name)

            provider_combo.setCurrentIndex(0)
            provider_combo.currentIndexChanged.connect(
                lambda idx, k=key: self._on_provider_changed(k)
            )

            grid.addWidget(provider_combo, row, 1)
            self.provider_combos[key] = provider_combo

            # Model combo box
            model_combo = QComboBox()
            grid.addWidget(model_combo, row, 2)
            self.model_combos[key] = model_combo

            # Populate models for initial provider
            self._populate_models(key)

            # Connect model change signal
            model_combo.currentIndexChanged.connect(self._on_config_changed)

        self._apply_default_stage_config()
        layout.addWidget(group)

    def _on_provider_changed(self, stage_key: str):
        """Handle provider selection change - update model dropdown."""
        self._populate_models(stage_key)
        self._on_config_changed()

    def _populate_models(self, stage_key: str):
        """Populate the model dropdown for a given stage based on selected provider."""
        provider_combo = self.provider_combos[stage_key]
        model_combo = self.model_combos[stage_key]

        provider_name = provider_combo.currentData()
        if not provider_name:
            return

        try:
            provider = LLMProviderRegistry.get(provider_name)
            models = provider.get_models()
        except (ValueError, AttributeError):
            models = []

        # Block signals to avoid triggering config_changed multiple times
        model_combo.blockSignals(True)
        model_combo.clear()

        for model_id, display_name in models:
            model_combo.addItem(display_name, model_id)

        if models:
            model_combo.setCurrentIndex(0)

        model_combo.blockSignals(False)

    def _on_config_changed(self):
        """Emit signal when any selection changes."""
        self.config_changed.emit()

    def _apply_default_stage_config(self):
        """Apply the default provider/model selections for each stage."""
        for stage_key, (provider_name, model_id) in self.DEFAULT_STAGE_CONFIG.items():
            provider_combo = self.provider_combos.get(stage_key)
            if provider_combo:
                for i in range(provider_combo.count()):
                    if provider_combo.itemData(i) == provider_name:
                        provider_combo.setCurrentIndex(i)
                        break

            model_combo = self.model_combos.get(stage_key)
            if model_combo:
                for i in range(model_combo.count()):
                    if model_combo.itemData(i) == model_id:
                        model_combo.setCurrentIndex(i)
                        break

    def get_config(self) -> LLMConfig:
        """Get current LLM configuration."""
        return LLMConfig(
            question_gen=self.provider_combos["question_gen"].currentData(),
            description_molding=self.provider_combos["description_molding"].currentData(),
            research=self.provider_combos["research"].currentData(),
            task_planning=self.provider_combos["task_planning"].currentData(),
            coder=self.provider_combos["coder"].currentData(),
            reviewer=self.provider_combos["reviewer"].currentData(),
            fixer=self.provider_combos["fixer"].currentData(),
            unit_test_prep=self.provider_combos["unit_test_prep"].currentData(),
            git_ops=self.provider_combos["git_ops"].currentData(),
            client_message_handler=self.provider_combos["client_message_handler"].currentData(),
            question_gen_model=self.model_combos["question_gen"].currentData() or "",
            description_molding_model=self.model_combos["description_molding"].currentData() or "",
            research_model=self.model_combos["research"].currentData() or "",
            task_planning_model=self.model_combos["task_planning"].currentData() or "",
            coder_model=self.model_combos["coder"].currentData() or "",
            reviewer_model=self.model_combos["reviewer"].currentData() or "",
            fixer_model=self.model_combos["fixer"].currentData() or "",
            unit_test_prep_model=self.model_combos["unit_test_prep"].currentData() or "",
            git_ops_model=self.model_combos["git_ops"].currentData() or "",
            client_message_handler_model=self.model_combos["client_message_handler"].currentData() or "",
        )

    def get_config_dict(self) -> Dict[str, str]:
        """Get configuration as dictionary."""
        config = self.get_config()
        return {
            "question_gen": config.question_gen,
            "description_molding": config.description_molding,
            "research": config.research,
            "task_planning": config.task_planning,
            "coder": config.coder,
            "reviewer": config.reviewer,
            "fixer": config.fixer,
            "unit_test_prep": config.unit_test_prep,
            "git_ops": config.git_ops,
            "client_message_handler": config.client_message_handler,
            "question_gen_model": config.question_gen_model,
            "description_molding_model": config.description_molding_model,
            "research_model": config.research_model,
            "task_planning_model": config.task_planning_model,
            "coder_model": config.coder_model,
            "reviewer_model": config.reviewer_model,
            "fixer_model": config.fixer_model,
            "unit_test_prep_model": config.unit_test_prep_model,
            "git_ops_model": config.git_ops_model,
            "client_message_handler_model": config.client_message_handler_model,
        }

    def get_stage_config(self, stage_key: str) -> StageConfig:
        """Get provider and model for a specific stage."""
        return StageConfig(
            provider=self.provider_combos[stage_key].currentData(),
            model=self.model_combos[stage_key].currentData() or ""
        )

    def set_config(self, config: Dict[str, str]):
        """Set LLM configuration from dictionary."""
        # First set providers
        for key in ["question_gen", "description_molding", "research", "task_planning", "coder", "reviewer", "fixer", "unit_test_prep", "git_ops", "client_message_handler"]:
            if key in config and key in self.provider_combos:
                combo = self.provider_combos[key]
                for i in range(combo.count()):
                    if combo.itemData(i) == config[key]:
                        combo.setCurrentIndex(i)
                        break

        # Then set models (after providers are set to ensure model lists are populated)
        for key in ["question_gen", "description_molding", "research", "task_planning", "coder", "reviewer", "fixer", "unit_test_prep", "git_ops", "client_message_handler"]:
            model_key = f"{key}_model"
            if model_key in config and key in self.model_combos:
                combo = self.model_combos[key]
                for i in range(combo.count()):
                    if combo.itemData(i) == config[model_key]:
                        combo.setCurrentIndex(i)
                        break

    def set_all_to(self, llm_name: str, model: Optional[str] = None):
        """Set all stages to use the same LLM and optionally the same model."""
        for key in self.provider_combos:
            combo = self.provider_combos[key]
            for i in range(combo.count()):
                if combo.itemData(i) == llm_name:
                    combo.setCurrentIndex(i)
                    break

            # If model specified, set it after provider change
            if model:
                model_combo = self.model_combos[key]
                for i in range(model_combo.count()):
                    if model_combo.itemData(i) == model:
                        model_combo.setCurrentIndex(i)
                        break

    def set_enabled(self, enabled: bool):
        """Enable or disable all combos."""
        for combo in self.provider_combos.values():
            combo.setEnabled(enabled)
        for combo in self.model_combos.values():
            combo.setEnabled(enabled)
