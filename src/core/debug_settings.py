"""Shared debug settings defaults and helpers."""

from typing import Any, Dict


DEBUG_STAGE_LABELS: Dict[str, str] = {
    "question_generation": "Question Generation",
    "description_molding": "Description Molding",
    "research": "Research",
    "task_planning": "Task Planning",
    "execution": "Task Execution",
    "reviewer": "Reviewer",
    "fixer": "Fixer",
    "git_commit": "Git Commit",
    "git_push": "Git Push",
}


def default_debug_breakpoints() -> Dict[str, Dict[str, bool]]:
    """Return default before/after breakpoint selections per stage."""
    return {
        stage: {"before": True, "after": False}
        for stage in DEBUG_STAGE_LABELS
    }


def normalize_debug_breakpoints(value: Any) -> Dict[str, Dict[str, bool]]:
    """Normalize persisted breakpoint data into expected shape."""
    normalized = default_debug_breakpoints()
    if not isinstance(value, dict):
        return normalized

    for stage, stage_config in value.items():
        if stage not in normalized or not isinstance(stage_config, dict):
            continue
        normalized[stage]["before"] = bool(stage_config.get("before", False))
        normalized[stage]["after"] = bool(stage_config.get("after", False))

    return normalized
