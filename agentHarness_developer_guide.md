# AgentHarness Developer Guide (Repo Root)

## Purpose
AgentHarness is a PySide6 desktop app that runs a multi-phase, LLM-driven development workflow. This guide explains entry points, runtime artifacts, and where to implement common changes.

## Top-Level Map
- `main.py`: Application entry point. Creates `QApplication` and shows `MainWindow`.
- `src/`: All application code (GUI, core workflow, workers, LLM integration, utils).
- `TODO's`: Product backlog and feature notes that map into code.
- `Product Description`: Product vision and UX goals.
- `requirements.txt`: Runtime dependencies (PySide6).
- `AGENTS.md`: Repo-specific assistant rules.
- `CLAUDE.md`: Workflow notes and architecture overview.
- `.gitignore`: Ignore rules (keep temp dirs ignored).
- `.idea/`, `.claude/`, `.venv/`, `.git/`: Local tools, settings, and VCS metadata.

## Workflow Overview (High Level)
1. UI collects description, LLM choices, and execution settings.
2. `StateMachine` tracks phase/context; `MainWindow` dispatches workers.
3. Question generation (prefetch + single-question loop).
4. Task planning writes `description.md` and `tasks.md`.
5. Main execution completes one task per iteration and updates `recent-changes.md`.
6. Review loop writes `review.md` and runs fixer.
7. Git operations optionally commit and push.

## Working-Directory Artifacts
Created in the selected working directory (not the repo root):
- `tasks.md`: Task checklist and completion state.
- `recent-changes.md`: Rolling log of code changes.
- `review.md`: Reviewer findings for the fixer.
- `description.md`: LLM-generated full project spec.
- `session_state.json`: Pause/resume snapshot of workflow state.
- `questions.json`: Batch questions file.
- `single_question.json`: Last generated single question (iterative path).

## TODO-to-File Map
Use this when picking up items from `TODO's`.
- Save full session state / resume later: `src/core/session_manager.py`, `src/core/state_machine.py`, `src/gui/main_window.py`, `src/gui/widgets/config_panel.py`.
- Warn when debug loop iterations are 0 at Start: `src/gui/main_window.py`, `src/gui/widgets/config_panel.py`.
- Detect Gemini quota errors and prompt for LLM switch: `src/workers/llm_worker.py`, `src/llm/gemini_provider.py`, `src/core/exceptions.py`, `src/gui/main_window.py`.
- Detect Claude quota errors and prompt for LLM switch: `src/workers/llm_worker.py`, `src/llm/claude_provider.py`, `src/core/exceptions.py`, `src/gui/main_window.py`.
- Add UI/UX review type: `src/llm/prompt_templates.py`, `src/core/state_machine.py`, `src/core/project_settings.py`, `src/gui/widgets/config_panel.py`, `src/workers/review_worker.py`.
- Flag files per step and skip review iterations on "all clear": `src/core/file_manager.py`, `src/workers/review_worker.py`, `src/gui/main_window.py`.
- Reset state on app relaunch (clear questions.json, etc): `src/gui/main_window.py`, `src/core/file_manager.py`, `src/workers/question_worker.py`.
- Show generated description and task checklist/progress in UI: `src/workers/planning_worker.py`, `src/gui/widgets/description_panel.py`, `src/gui/widgets/status_panel.py`, `src/gui/main_window.py`.
- Allow changing LLM per stage during run: `src/gui/main_window.py`, `src/gui/widgets/llm_selector_panel.py`, `src/core/state_machine.py`.
- Fix log filtering for existing log lines: `src/gui/widgets/log_viewer.py`.
- Planning loop with multiple passes: `src/workers/planning_worker.py`, `src/gui/main_window.py`, `src/llm/prompt_templates.py`.
- Allow new prompt after completion and re-enable controls: `src/gui/main_window.py`, `src/core/state_machine.py`.
- Enforce .md + <1000 LOC rules and auto-create CLAUDE/AGENTS/GEMINI files: `src/llm/prompt_templates.py`, `src/core/file_manager.py`, `src/workers/execution_worker.py`, `src/gui/main_window.py`.
- Ensure fixer updates recent-changes.md when it edits code: `src/llm/prompt_templates.py`, `src/workers/review_worker.py`.
- Handle UI app runs that block (timeouts or guidance): `src/llm/prompt_templates.py`, `src/workers/llm_worker.py`.
- Keep recent-changes.md capped (no reset each task): `src/core/file_manager.py`, `src/gui/main_window.py`.
- UI action to add tasks: `src/gui/widgets/config_panel.py`, `src/gui/main_window.py`, `src/utils/markdown_parser.py`, `src/core/file_manager.py`.
- Update questions.json when answers are submitted: `src/gui/main_window.py`, `src/workers/question_worker.py`, `src/core/question_prefetch_manager.py`.
- Review prompts should leave review.md empty when no issues: `src/llm/prompt_templates.py`, `src/workers/review_worker.py`.
- Investigate slowness (timeouts/sequencing): `src/workers/llm_worker.py`, `src/gui/main_window.py`, `src/workers/`.
- Stop review loop early when all reviews empty: `src/workers/review_worker.py`, `src/gui/main_window.py`.
- Multi-LLM review pipelines: `src/gui/widgets/llm_selector_panel.py`, `src/gui/widgets/config_panel.py`, `src/workers/review_worker.py`, `src/core/state_machine.py`, `src/core/project_settings.py`.
- Add more LLMs/models and API key handling: `src/llm/base_provider.py`, `src/llm/*_provider.py`, `src/gui/widgets/llm_selector_panel.py`, `src/core/project_settings.py`.
- Review ordering (general to specific): `src/llm/prompt_templates.py`, `src/workers/review_worker.py`.
- Continue after completion (more iterations or new feature): `src/gui/main_window.py`, `src/core/state_machine.py`, `src/gui/widgets/config_panel.py`.
- Capture UI screenshots for debugging: `src/gui/main_window.py`, `src/gui/widgets/log_viewer.py`.
- Let LLM choose review types dynamically: `src/llm/prompt_templates.py`, `src/workers/review_worker.py`, `src/gui/widgets/config_panel.py`.
- Dedicated "add tasks" pass after iterations: `src/workers/execution_worker.py` (or new worker), `src/utils/markdown_parser.py`, `src/core/file_manager.py`, `src/gui/main_window.py`.

## Change Map
- App startup: `main.py`, `src/gui/main_window.py`.
- Workflow state and persistence: `src/core/state_machine.py`, `src/core/session_manager.py`.
- LLM prompts and providers: `src/llm/`.
- Background phase logic: `src/workers/`.
- UI/UX components: `src/gui/`.
