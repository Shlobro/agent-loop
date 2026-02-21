# src Developer Guide

## Purpose
Application source package for AgentHarness. This is where the workflow, UI, LLM integration, and parsing live.

## Folder Map
- `core/`: Phase state machine, debug settings defaults, session persistence, file I/O, and settings models.
- `gui/`: Main window orchestration, centralized theme (`gui/theme.py`), and UI panels/dialogs.
- `llm/`: CLI-based LLM providers (Claude, Gemini, Codex). Codex supports reasoning effort levels (low, medium, high, xhigh) via model ID suffixes (e.g., `gpt-5.3-codex:high`) and, when a working directory is provided, pins sandbox scope with `--cd <working_directory>` plus `--add-dir <working_directory>` so file writes target the selected project tree. Provider-agnostic prompt templates ensure consistent instruction formatting.
- `utils/`: Common parsing utilities for JSON, Markdown, and other formats.
- `workers/`: QRunnable workers for each workflow phase (LLM runner logs full prompts, emits output-file content to the log, supports per-stage debug breakpoints before/after each LLM call, can show/hide Windows live terminal popups per setting, and validates subprocess cwd with a safe fallback when a configured working directory is invalid). LLM defaults use longer time budgets: 600-second base timeout and 1200-second execution-stage timeout override.
- `__init__.py`: Package marker; importing `src.llm` registers providers.

## Phase-to-File Map
- Question generation: `workers/question_worker.py` (loads questions only from `questions.json` on a single LLM attempt; no stdout parsing or fallback prompts; rewrites Q&A into `product-description.md` before additional batches and reads that file back; rewrite content is accepted only from `product-description.md`, not stdout), `gui/dialogs/question_answer_dialog.py` (modal keyboard-driven answering window: Up/Down answers, Left/Right question navigation, Enter submit/advance and close on last question; manual close paths are blocked until final submit), `gui/dialogs/question_flow_decision_dialog.py` (non-modal post-rewrite chooser that keeps flow paused until user explicitly picks `Ask More Questions` or `Start Main Loop`), `gui/widgets/question_panel.py` (hidden signal bridge that opens the question dialog, emits submitted pairs, and routes post-rewrite branching through the decision dialog), `gui/main_window.py` (keeps `product-description.md` synced with the description widget, force-syncs GUI -> file before each question batch and before planning, initializes empty `questions.json` before each batch, rewrites only the currently submitted Q&A batch into `product-description.md` immediately after submission via the dedicated `description_molding` LLM selection, applies the rewrite result to the UI from `product-description.md` only in that rewrite step, clears stored Q&A/answers after rewrite so the rewritten description is the new baseline, unlocks description editing after the rewrite completes, rechecks git initialization before transitioning to planning, generates another question batch using the current GUI description and current question-count setting, and updates chat activity with animated `Generating questions...` status while the question worker runs), `llm/prompt_templates.py` (description-only question prompts that edit the empty `questions.json`, plus the Q&A-to-definition rewrite prompt that writes `product-description.md` via `PromptTemplates.format_definition_rewrite_prompt`).
- Working-directory resume detection: `gui/main_window.py` checks `tasks.md` when the working directory changes; when incomplete checklist items exist it prompts the user to resume, and an accepted resume starts directly in `Phase.MAIN_EXECUTION` instead of regenerating questions/plans.
- Task planning: `workers/planning_worker.py`, `llm/prompt_templates.py`, `core/file_manager.py` (planning writes `tasks.md` first, then runs a research pass that fills `research.md` using `product-description.md` plus `tasks.md` context).
- Main execution: `workers/execution_worker.py`, `llm/prompt_templates.py`, `core/file_manager.py`, `utils/markdown_parser.py`, `gui/widgets/task_loop_panel.py`, `gui/widgets/status_panel.py`, `gui/main_window.py` (loop UI highlights current action plus Markdown-rendered completed/incomplete task lists and task-count-based progress; progress is phase-weighted during each active execution/review/git cycle so new task completion reaches full credit only after git completes. Execution worker results include completed task titles so workflow chat can list what was completed).
- Chat progress messaging and activity animation: `gui/main_window.py` (phase/status -> friendly rotating activity text selection with larger per-phase phrase pools across question/planning/execution/review/git/client-message contexts) + `gui/widgets/chat_panel.py` (spinner animation and rotating activity text rendering). Client-message completion paths clear chat activity explicitly to avoid stale in-progress indicators, and when `answer.md` remains empty they now always emit a result bubble (Description tab guidance, Tasks tab guidance, or `nothing done` when no files changed).
- Main-loop git handoff robustness: `gui/workflow_runner.py` now guards post-git task checks against malformed worker results and `tasks.md` read failures, attempts file recovery via `FileManager.ensure_files_exist()`, and surfaces unexpected exceptions as explicit workflow errors instead of silently stalling. The same mixin also refreshes task snapshot UI immediately when chat-driven updates modify `tasks.md`, and posts phase-completion chat milestone messages (task planning, task execution summaries, unit-test validation, review completion, and git completion).
- Review loop: `workers/review_worker.py`, `llm/prompt_templates.py`, `core/file_manager.py`, `gui/main_window.py` (runs an optional pre-review unit-test-update pass, includes active review types such as General/Functionality/Architecture/Efficiency/Error Handling/Safety/Testing/Documentation/UI-UX, pre-creates per-type review files under `review/` when a valid working directory becomes active, skips fixer when the active review file is empty, and re-reads review iteration limit plus reviewer/fixer/unit-test-prep LLM selections between cycles).
- Git operations: `workers/git_worker.py`, `llm/prompt_templates.py`, `core/file_manager.py` (code injects `git status --porcelain` and `git diff` into the commit-message prompt, LLM writes only `.agentharness/git-commit-message.txt`; file is initialized at startup, git add/commit/push are executed by code, and the message file is truncated after commit).
- Pause/resume: `core/session_manager.py`, `core/state_machine.py`, `gui/main_window.py`.
- Debug step mode and stage breakpoints: `core/debug_settings.py`, `gui/dialogs/debug_settings_dialog.py`, `gui/main_window.py`, `workers/llm_worker.py`.

## When to Edit What
- UI layout or control wiring: `gui/main_window.py` plus panels in `gui/widgets/` and `gui/dialogs/` (`File -> Open Project...`, `Settings -> Configuration Settings`, `Settings -> LLM Settings`, `Settings -> Review Settings` with separate pre-review prep vs review-loop type sections, and `Settings -> Debug Settings` are wired in `main_window.py`). `main_window.py` also owns the minimalist default shell (`Product Description` header + one input area) and menu-driven workflow/view controls.
- Global look-and-feel, typography scale, button variants, Markdown display widget styling, and lightweight fade motion: `gui/theme.py`.
- Settings persistence and debug settings menu actions (including left logs-panel visibility; default hidden): `gui/settings_mixin.py` (invoked by `MainWindow`).
- Working-directory git bootstrap and remote auto-configuration at startup/runtime: `gui/widgets/config_panel.py` (git subprocess timeout: 10 seconds).
- Worker execution routing in the GUI: `gui/workflow_runner.py`.
- Review label display formatting in logs/activity: `gui/main_window.py` (uses `PromptTemplates.get_review_display_name`).
- New runtime settings or persistence: `core/project_settings.py` and `gui/widgets/config_panel.py`.
- Add new LLM provider/model or CLI flags (including output-file capture and prompt transport mode): `llm/*_provider.py` plus `gui/widgets/llm_selector_panel.py` and `gui/dialogs/llm_settings_dialog.py`. Provider files hold the curated model ID lists shown in the settings dialog; Claude, Gemini, and Codex send prompts via stdin. `llm_settings_dialog.py` also manages import/export of reusable stage-level LLM config JSON files.
- Change default per-stage provider/model selections (including the post-planning `research` stage): `gui/widgets/llm_selector_panel.py` (UI defaults) and `core/state_machine.py` (`StateContext` fallback defaults).
- Task list parsing or mutation rules: `utils/markdown_parser.py`.
- Change phase sequencing or transitions: `core/state_machine.py` and `gui/main_window.py`.

## How It Fits
`main.py` first requires a startup working-directory selection (with recent-directory shortcuts), then instantiates `gui/main_window.py`. During runtime, `File -> Open Project...` uses the same picker flow to switch projects. The GUI coordinates workers, which call into core utilities and LLM providers to drive the multi-phase workflow.

## Change Map
- Core workflow or persistence: `core/`.
- UI panels or orchestration: `gui/`.
- LLM adapters or prompts: `llm/`.
- Parsing helpers: `utils/`.
- Phase execution logic: `workers/`.


