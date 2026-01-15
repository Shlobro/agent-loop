"""Project settings manager for saving and loading project configurations."""

import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any


@dataclass
class ProjectSettings:
    """Project-specific settings that can be saved and loaded."""
    # LLM Configuration
    question_gen: str
    task_planning: str
    coder: str
    reviewer: str
    fixer: str
    git_ops: str
    question_gen_model: str = ""
    task_planning_model: str = ""
    coder_model: str = ""
    reviewer_model: str = ""
    fixer_model: str = ""
    git_ops_model: str = ""

    # Execution Configuration
    max_main_iterations: int = 50
    debug_loop_iterations: int = 5
    max_questions: int = 20
    auto_push: bool = False

    # Project Configuration
    working_directory: str = ""
    git_remote: str = ""


class ProjectSettingsManager:
    """Manages saving and loading of project settings."""

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

            return ProjectSettings(**settings_dict)
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
        return ProjectSettings(**settings_dict)
