# src Developer Guide

## Purpose
Application source package for AgentHarness. This is where the workflow, UI, LLM integration, and parsing live.

## Folder Map
- `core/`: Phase state machine, debug settings defaults, session persistence, file I/O, and settings models.
- `gui/`: Main window orchestration and UI panels.
- `llm/`: Provider adapters and prompt templates for every phase.
- `utils/`: Parsers for LLM output and markdown task lists.
- `workers/`: QRunnable workers for each workflow phase (LLM runner logs full prompts, emits output-file content to the log, supports per-stage debug breakpoints before/after each LLM call, and can show/hide Windows live terminal popups per setting).
- `__init__.py`: Package marker; importing `src.llm` registers providers.

## Phase-to-File Map
- Question generation: `workers/question_worker.py` (loads questions only from `questions.json` on a single LLM attempt; no stdout parsing or fallback prompts; rewrites Q&A into `product-description.md` before additional batches and reads that file back; rewrite content is accepted only from `product-description.md`, not stdout), `gui/dialogs/question_answer_dialog.py` (modal keyboard-driven answering window: Up/Down answers, Left/Right question navigation, Enter submit/advance and close on last question; manual close paths are blocked until final submit), `gui/widgets/question_panel.py` (hidden signal bridge that opens the dialog and emits submitted pairs), `gui/main_window.py` (keeps `product-description.md` synced with the description widget, force-syncs GUI -> file before each question batch and before planning, initializes empty `questions.json` before each batch, rewrites only the currently submitted Q&A batch into `product-description.md` immediately after submission via the dedicated `description_molding` LLM selection, applies the rewrite result to the UI from `product-description.md` only in that rewrite step, clears stored Q&A/answers after rewrite so the rewritten description is the new baseline, unlocks description editing after the rewrite completes, rechecks git initialization before transitioning to planning, and generates another question batch using the current GUI description and current question-count setting), `llm/prompt_templates.py` (description-only question prompts that edit the empty `questions.json`, plus the Q&A-to-definition rewrite prompt that writes `product-description.md` via `PromptTemplates.format_definition_rewrite_prompt`).
- Working-directory resume detection: `gui/main_window.py` checks `tasks.md` when the working directory changes; when incomplete checklist items exist it prompts the user to resume, and an accepted resume starts directly in `Phase.MAIN_EXECUTION` instead of regenerating questions/plans.
- Task planning: `workers/planning_worker.py`, `llm/prompt_templates.py`, `core/file_manager.py` (planning prompts instruct the LLM to write directly to `tasks.md` based on the project description, preferring `product-description.md` when present).
- Main execution: `workers/execution_worker.py`, `llm/prompt_templates.py`, `core/file_manager.py`, `utils/markdown_parser.py`.
- Review loop: `workers/review_worker.py`, `llm/prompt_templates.py`, `core/file_manager.py`, `gui/main_window.py` (runs an optional pre-review unit-test-update pass, includes active review types such as General/Architecture/Efficiency/Error Handling/Safety/Testing/Documentation/UI-UX, pre-creates per-type review files under `review/` when a valid working directory becomes active, skips fixer when the active review file is empty, and re-reads review iteration limit plus reviewer/fixer/unit-test-prep LLM selections between cycles).
- Git operations: `workers/git_worker.py`, `llm/prompt_templates.py`, `core/file_manager.py` (code injects `git status --porcelain` and `git diff` into the commit-message prompt, LLM writes only `.agentharness/git-commit-message.txt`; file is initialized at startup, git add/commit/push are executed by code, and the message file is truncated after commit).
- Pause/resume: `core/session_manager.py`, `core/state_machine.py`, `gui/main_window.py`.
- Debug step mode and stage breakpoints: `core/debug_settings.py`, `gui/dialogs/debug_settings_dialog.py`, `gui/main_window.py`, `workers/llm_worker.py`.

## When to Edit What
- UI layout or control wiring: `gui/main_window.py` plus panels in `gui/widgets/` and `gui/dialogs/` (`Settings -> Configuration Settings`, `Settings -> LLM Settings`, `Settings -> Review Settings`, and `Settings -> Debug Settings` are wired in `main_window.py`).
- Settings persistence and debug settings menu actions (including left logs-panel visibility): `gui/settings_mixin.py` (invoked by `MainWindow`).
- Working-directory git bootstrap and remote auto-configuration at startup/runtime: `gui/widgets/config_panel.py`.
- Worker execution routing in the GUI: `gui/workflow_runner.py`.
- Review label display formatting in logs/activity: `gui/main_window.py` (uses `PromptTemplates.get_review_display_name`).
- New runtime settings or persistence: `core/project_settings.py` and `gui/widgets/config_panel.py`.
- Add new LLM provider/model or CLI flags (including output-file capture and prompt transport mode): `llm/*_provider.py` plus `gui/widgets/llm_selector_panel.py` and `gui/dialogs/llm_settings_dialog.py`. Provider files hold the curated model ID lists shown in the settings dialog; Claude, Gemini, and Codex send prompts via stdin.
- Change default per-stage provider/model selections: `gui/widgets/llm_selector_panel.py` (UI defaults) and `core/state_machine.py` (`StateContext` fallback defaults).
- Task list parsing or mutation rules: `utils/markdown_parser.py`.
- Change phase sequencing or transitions: `core/state_machine.py` and `gui/main_window.py`.

## How It Fits
`main.py` first requires a startup working-directory selection (with recent-directory shortcuts), then instantiates `gui/main_window.py`. The GUI coordinates workers, which call into core utilities and LLM providers to drive the multi-phase workflow.

## Change Map
- Core workflow or persistence: `core/`.
- UI panels or orchestration: `gui/`.
- LLM adapters or prompts: `llm/`.
- Parsing helpers: `utils/`.
- Phase execution logic: `workers/`.
