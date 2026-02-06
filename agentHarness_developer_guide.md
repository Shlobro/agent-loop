# AgentHarness Developer Guide (Repo Root)

## Purpose
AgentHarness is a PySide6 desktop app that runs a multi-phase, LLM-driven development workflow. This guide explains entry points, runtime artifacts, and where to implement common changes.

## Top-Level Map
- `main.py`: Application entry point. Creates `QApplication` and shows `MainWindow`.
- `src/`: All application code (GUI, core workflow, workers, LLM integration, utils).
- `test.txt`: simple text placeholder currently containing a greeting string.
- `TODO's`: Product backlog and feature notes that map into code.
- `Product Description`: Product vision and UX goals.
- `requirements.txt`: Runtime dependencies (PySide6).
- `AGENTS.md`: Repo-specific assistant rules.
- `CLAUDE.md`: Workflow notes and architecture overview.
- `GEMINI.md`: Workflow notes and architecture overview for Gemini.
- `.gitignore`: Ignore rules (keep temp dirs ignored).
- `.idea/`, `.claude/`, `.venv/`, `.git/`: Local tools, settings, and VCS metadata.

## Workflow Overview (High Level)
1. UI collects description, LLM choices, and execution settings. Review type selection is exposed through the top menu `Settings -> Review Settings`. The description is synced to `product-description.md`, and the GUI value is force-written to that file before each question batch and before planning. After answers are submitted, only the current Q&A batch is rewritten into `product-description.md` using `PromptTemplates.format_definition_rewrite_prompt`; only this rewrite step pushes file content back into the GUI. Stored Q&A context is then cleared so the rewritten description is treated as the new initial input. The description then becomes editable again, and only then can the user generate more questions or start planning.
2. When a working directory is selected (including the startup default), UI config handling ensures the directory is a git repo (`git init` if needed), surfaces a user-facing notice when git is missing, and configures `origin` if a remote URL is set.
3. `StateMachine` tracks phase/context; `MainWindow` dispatches workers.
4. Question generation initializes an empty `questions.json` and expects the LLM to write a batch into it in a single attempt (no stdout parsing or fallback prompts); generating another batch deletes the previous `questions.json`.
5. Description molding runs after answers are submitted: it rewrites Q&A plus the current description into `product-description.md` using the dedicated `description_molding` stage/model; this step is file-first (`product-description.md` updates the UI, not the other way around).
6. Task planning reads `product-description.md` when available and has the LLM write directly to `tasks.md`.
7. Main execution completes one task per iteration and updates `recent-changes.md`.
   - Execution and fixer prompts include workspace governance rules plus a compliance scan summary (fresh scan each execution/review cycle):
     - Always start by reading `product-description.md`.
     - Each folder must have a `developer-guide.md` (updated after any change, create if missing) to allow understanding without reading code.
     - Read the developer guide in the folder you are editing before making changes.
     - Update the relevant developer guides and their ancestors when behavior changes.
     - No legacy information in developer guides.
     - No more than 10 code files per folder (`.md` files do not count).
     - No code file over 1000 lines.
     - Developer guides must be under 500 lines (compact if needed while preserving info).
8. Review loop (including General, Unit Test, and UI/UX review types) writes `review.md` and runs fixer.
9. Git operations optionally commit and push.
10. Debug step mode is controlled from `Settings -> Debug Settings`: stage-specific before/after breakpoints pause right before or right after each LLM call until the user clicks `Next Step`.
11. A debug setting controls whether per-call live terminal windows are shown on Windows.

## Working-Directory Artifacts
Created in the selected working directory (not the repo root):
- `tasks.md`: Task checklist and completion state.
- `recent-changes.md`: Rolling log of code changes.
- `review.md`: Reviewer findings for the fixer.
- `product-description.md`: Synced project description from the UI.
- `product-description.md`: Q&A-rewritten product definition used for task planning.
- `session_state.json`: Pause/resume snapshot of workflow state.
- `questions.json`: Batch questions file.
- `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`: Governance prompt files; auto-created if missing.
- `.agentharness/live-llm/*.log`: Per-run live output logs used to mirror LLM execution into popup terminal windows.

## TODO-to-File Map
Use this when picking up items from `TODO's`.
- Save full session state / resume later: `src/core/session_manager.py`, `src/core/state_machine.py`, `src/gui/main_window.py`, `src/gui/widgets/config_panel.py`.
- Warn when debug loop iterations are 0 at Start: `src/gui/main_window.py`, `src/gui/widgets/config_panel.py`.
- Detect Gemini quota errors and prompt for LLM switch: `src/workers/llm_worker.py`, `src/llm/gemini_provider.py`, `src/core/exceptions.py`, `src/gui/main_window.py`.
- Detect Claude quota errors and prompt for LLM switch: `src/workers/llm_worker.py`, `src/llm/claude_provider.py`, `src/core/exceptions.py`, `src/gui/main_window.py`.
- Add or adjust review types/settings UI: `src/llm/prompt_templates.py`, `src/core/state_machine.py`, `src/core/project_settings.py`, `src/gui/widgets/config_panel.py`, `src/gui/dialogs/review_settings_dialog.py`, `src/workers/review_worker.py`.
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
- Update questions.json when answers are submitted: `src/gui/main_window.py`, `src/workers/question_worker.py`.
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
- LLM provider CLI flags, commands, and curated model IDs used by the UI: `src/llm/*_provider.py`.
- Default per-stage LLM provider/model assignments (including `description_molding`): `src/gui/widgets/llm_selector_panel.py` (UI defaults) and `src/core/state_machine.py` (`StateContext` fallback).
- LLM output capture and prompt transport behavior (argv vs stdin/output-file): `src/workers/llm_worker.py`, `src/llm/*_provider.py` (Claude and Gemini use stdin prompts).
- Debug stepping/breakpoints and terminal popup visibility: `src/core/debug_settings.py`, `src/gui/dialogs/debug_settings_dialog.py`, `src/gui/main_window.py`, `src/workers/llm_worker.py`.
- Review label formatting in UI/logs: `src/gui/main_window.py` (uses `PromptTemplates.get_review_display_name`).
- Background phase logic: `src/workers/`.
- UI/UX components: `src/gui/`.
- GUI worker orchestration: `src/gui/main_window.py`, `src/gui/workflow_runner.py`.
- Settings save/load and debug settings menu wiring: `src/gui/settings_mixin.py`.
