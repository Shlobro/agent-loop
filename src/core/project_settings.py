"""Project settings manager for saving and loading project configurations."""

import json
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List

from .debug_settings import default_debug_breakpoints, normalize_debug_breakpoints
from ..llm.prompt_templates import ReviewType


@dataclass
class ProjectSettings:
    """Project-specific settings that can be saved and loaded."""
    # LLM Configuration
    question_gen: str
    description_molding: str
    task_planning: str
    coder: str
    reviewer: str
    fixer: str
    unit_test_prep: str = "gemini"
    git_ops: str = "gemini"
    question_gen_model: str = ""
    description_molding_model: str = "gemini-3-pro-preview"
    task_planning_model: str = ""
    coder_model: str = ""
    reviewer_model: str = ""
    fixer_model: str = ""
    unit_test_prep_model: str = "gemini-3-pro-preview"
    git_ops_model: str = ""
    review_types: List[str] = field(
        default_factory=lambda: [ReviewType.GENERAL.value]
    )
    run_unit_test_prep: bool = True
    tasks_per_iteration: int = 1

    # Execution Configuration
    max_main_iterations: int = 10
    debug_loop_iterations: int = 1
    debug_mode_enabled: bool = False
    debug_breakpoints: Dict[str, Dict[str, bool]] = field(default_factory=default_debug_breakpoints)
    show_llm_terminals: bool = True
    show_logs_panel: bool = True
    max_questions: int = 5
    git_mode: str = "local"

    # Project Configuration
    working_directory: str = ""
    git_remote: str = ""


class ProjectSettingsManager:
    """Manages saving and loading of project settings."""
    WORKING_DIR_SETTINGS_SUBDIR = ".agentharness"
    WORKING_DIR_SETTINGS_FILE = "project-settings.json"

    @staticmethod
    def save_to_file(settings: ProjectSettings, file_path: str) -> None:
        """
        Save project settings to a JSON file.

        Args:
            settings: ProjectSettings object to save
            file_path: Path to save the settings file
        """
        settings_dict = asdict(settings)

        try:
            path = Path(file_path)
            with path.open('w', encoding='utf-8') as f:
                json.dump(settings_dict, f, indent=2)
        except Exception as e:
            raise RuntimeError(f"Failed to save settings: {e}")

    @staticmethod
    def get_working_directory_settings_path(working_directory: str) -> Path:
        """Return the per-directory settings file path."""
        return (
            Path(working_directory)
            / ProjectSettingsManager.WORKING_DIR_SETTINGS_SUBDIR
            / ProjectSettingsManager.WORKING_DIR_SETTINGS_FILE
        )

    @staticmethod
    def has_working_directory_settings(working_directory: str) -> bool:
        """Return True when a per-directory settings file exists."""
        if not working_directory:
            return False
        return ProjectSettingsManager.get_working_directory_settings_path(working_directory).exists()

    @staticmethod
    def save_for_working_directory(settings: ProjectSettings, working_directory: str) -> None:
        """Save settings in `.agentharness/project-settings.json` for a working directory."""
        if not working_directory:
            raise RuntimeError("Working directory is required to save settings.")
        settings_path = ProjectSettingsManager.get_working_directory_settings_path(working_directory)
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        ProjectSettingsManager.save_to_file(settings, str(settings_path))

    @staticmethod
    def load_for_working_directory(working_directory: str) -> ProjectSettings:
        """Load settings from `.agentharness/project-settings.json` for a working directory."""
        if not working_directory:
            raise RuntimeError("Working directory is required to load settings.")
        settings_path = ProjectSettingsManager.get_working_directory_settings_path(working_directory)
        return ProjectSettingsManager.load_from_file(str(settings_path))

    @staticmethod
    def load_from_file(file_path: str) -> ProjectSettings:
        """
        Load project settings from a JSON file.

        Args:
            file_path: Path to the settings file

        Returns:
            ProjectSettings object loaded from file
        """
        try:
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"Settings file not found: {file_path}")

            with path.open('r', encoding='utf-8') as f:
                settings_dict = json.load(f)

            normalized = ProjectSettingsManager._normalize_settings_dict(settings_dict)
            return ProjectSettings(**normalized)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid settings file format: {e}")
        except TypeError as e:
            raise RuntimeError(f"Invalid settings data: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to load settings: {e}")

    @staticmethod
    def settings_to_dict(settings: ProjectSettings) -> Dict[str, Any]:
        """Convert ProjectSettings to dictionary."""
        return asdict(settings)

    @staticmethod
    def dict_to_settings(settings_dict: Dict[str, Any]) -> ProjectSettings:
        """Convert dictionary to ProjectSettings."""
        normalized = ProjectSettingsManager._normalize_settings_dict(settings_dict)
        return ProjectSettings(**normalized)

    @staticmethod
    def _normalize_settings_dict(settings_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize settings dict for backward compatibility."""
        field_names = {f.name for f in ProjectSettings.__dataclass_fields__.values()}
        normalized = {k: v for k, v in settings_dict.items() if k in field_names}

        if "git_mode" not in normalized:
            auto_push = settings_dict.get("auto_push", False)
            normalized["git_mode"] = "push" if auto_push else "local"
        if "description_molding" not in normalized:
            normalized["description_molding"] = "gemini"
        if "unit_test_prep" not in normalized:
            normalized["unit_test_prep"] = "gemini"
        if "description_molding_model" not in normalized:
            normalized["description_molding_model"] = "gemini-3-pro-preview"
        if "unit_test_prep_model" not in normalized:
            normalized["unit_test_prep_model"] = "gemini-3-pro-preview"
        if "debug_mode_enabled" not in normalized:
            normalized["debug_mode_enabled"] = False
        normalized["debug_breakpoints"] = normalize_debug_breakpoints(
            normalized.get("debug_breakpoints", {})
        )
        if "show_llm_terminals" not in normalized:
            normalized["show_llm_terminals"] = True
        if "show_logs_panel" not in normalized:
            normalized["show_logs_panel"] = True
        if "run_unit_test_prep" not in normalized:
            normalized["run_unit_test_prep"] = True
        if "tasks_per_iteration" not in normalized:
            normalized["tasks_per_iteration"] = 1

        return normalized
