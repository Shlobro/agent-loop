# src Developer Guide

## Purpose
Application source package for AgentHarness. This is where the workflow, UI, LLM integration, and parsing live.

## Folder Map
- `core/`: Phase state machine, session persistence, file I/O, and settings models.
- `gui/`: Main window orchestration and UI panels.
- `llm/`: Provider adapters and prompt templates for every phase.
- `utils/`: Parsers for LLM output and markdown task lists.
- `workers/`: QRunnable workers for each workflow phase.
- `__init__.py`: Package marker; importing `src.llm` registers providers.

## Phase-to-File Map
- Question generation: `core/question_prefetch_manager.py`, `workers/question_worker.py`, `gui/widgets/question_panel.py`, `llm/prompt_templates.py`.
- Task planning: `workers/planning_worker.py`, `llm/prompt_templates.py`, `core/file_manager.py`.
- Main execution: `workers/execution_worker.py`, `llm/prompt_templates.py`, `core/file_manager.py`, `utils/markdown_parser.py`.
- Review loop: `workers/review_worker.py`, `llm/prompt_templates.py`, `core/file_manager.py`.
- Git operations: `workers/git_worker.py`, `llm/prompt_templates.py`.
- Pause/resume: `core/session_manager.py`, `core/state_machine.py`, `gui/main_window.py`.

## When to Edit What
- UI layout or control wiring: `gui/main_window.py` plus panels in `gui/widgets/`.
- New runtime settings or persistence: `core/project_settings.py` and `gui/widgets/config_panel.py`.
- Add new LLM provider/model: `llm/*_provider.py` plus `gui/widgets/llm_selector_panel.py`.
- Task list parsing or mutation rules: `utils/markdown_parser.py`.
- Change phase sequencing or transitions: `core/state_machine.py` and `gui/main_window.py`.

## How It Fits
`main.py` instantiates `gui/main_window.py`. The GUI coordinates workers, which call into core utilities and LLM providers to drive the multi-phase workflow.

## Change Map
- Core workflow or persistence: `core/`.
- UI panels or orchestration: `gui/`.
- LLM adapters or prompts: `llm/`.
- Parsing helpers: `utils/`.
- Phase execution logic: `workers/`.
