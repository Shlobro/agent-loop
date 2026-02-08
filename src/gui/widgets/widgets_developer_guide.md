# widgets Developer Guide

## Purpose
Reusable PySide6 panels used by `MainWindow` to assemble the UI.

## Contents
- `description_panel.py`: Minimal-first project description surface. Default view shows a single header (`Product Description`) and one large input area. Markdown edit/preview behavior is still available and can be surfaced from `View` menu toggles in `MainWindow`; changes are synced to `product-description.md`.
- `question_panel.py`: Hidden signal bridge for question flow. It opens `dialogs/question_answer_dialog.py` as a modal window when questions are ready, emits submitted Q&A pairs, and then opens `dialogs/question_flow_decision_dialog.py` after rewrite so the user explicitly chooses `Ask More Questions` or `Start Main Loop`.
- `llm_selector_panel.py`: Provider/model selection per workflow stage from the LLM registry, including built-in default stage assignments; hosted by `Settings -> LLM Settings` and used as the canonical in-memory stage config for the run. Stages are displayed in execution order, with Unit Test Prep shown before Reviewer and Fixer to reflect that it runs first in the review phase.
- `config_panel.py`: Execution settings (iterations, tasks per iteration, questions, working directory, git settings), stored review-type selections, and the optional pre-review unit-test-update toggle used by the review settings dialog; hosted by `Settings -> Configuration Settings`, while values stay live-editable during execution.
- `log_viewer.py`: Color-coded log viewer with filtering and auto-scroll; uses an enlarged monospace font for clearer streaming output.
- `status_panel.py`: Top-line workflow status, iteration label, and top-right progress bar; progress is task-list based (`completed tasks / total tasks`) during loop execution.
- `task_loop_panel.py`: Main-loop priority panel that shows the current agent action plus completed/incomplete task counts and Markdown-rendered task lists.
- `__init__.py`: Module marker.

## Key Interactions
- Widgets use the centralized stylesheet from `src/gui/theme.py`; prefer setting widget properties (for example `role="muted"`) instead of hardcoded inline colors.
- `LLMSelectorPanel` queries `LLMProviderRegistry` to populate providers/models and then applies stage defaults (in execution order):
- Question generation: Gemini + `gemini-3-pro-preview`
- Description molding: Gemini + `gemini-3-pro-preview`
- Task planning: Claude + `claude-opus-4-6`
- Coder: Claude + `claude-opus-4-6`
- Unit Test Prep (runs first in review): Gemini + `gemini-3-pro-preview`
- Reviewer: Codex + `gpt-5.3-codex`
- Fixer: Codex + `gpt-5.3-codex`
- Git operations: Gemini + `gemini-3-pro-preview`
- `ConfigPanel` exposes `ExecutionConfig`; review type selections are edited through the main menu action `Settings -> Review Settings` and include all active review categories (General, Architecture, Efficiency, Error Handling, Safety, Testing, Documentation, UI/UX). The same dialog also controls whether the optional pre-review unit-test-update pass runs.
- `ConfigPanel` keeps `Number of Questions`, `Max Main Iterations`, `Tasks Per Iteration`, and `Debug Loop Iterations` enabled during active runs so users can change upcoming question batches, loop limits, and tasks-per-iteration without stopping.
- `ConfigPanel` performs git bootstrap checks for the selected working directory both when the directory/remote changes and when planning starts: checks whether the directory is already a git repo, runs `git init` when needed, shows a user-facing install notice if git commands are unavailable/fail, and configures `origin` when a remote URL is set.
- `QuestionPanel` remains connected to `MainWindow` signal wiring but is not used as a visible section in the main layout.
- `DescriptionPanel` keeps a Markdown preview surface in sync with editor text via `QTextBrowser.setMarkdown(...)` and swaps editor/preview in the same box through a `QStackedWidget`; the explicit `Edit`/`Preview` controls are hidden by default and can be enabled from the `View` menu.
- `TaskLoopPanel` renders completed/incomplete lists in Markdown-capable `QTextBrowser` widgets so task text formatting is preserved.
- `LogViewer` listens to worker log and LLM output signals from `MainWindow`.

## When to Edit Widgets
- Add or adjust review selection behavior: `config_panel.py` and `../dialogs/review_settings_dialog.py`.
- Change per-stage LLM selector behavior or enable runtime edits: `llm_selector_panel.py`.
- Adjust visual tone for logs/status/description surfaces while preserving behavior: `description_panel.py`, `log_viewer.py`, `status_panel.py`, and shared styles in `../theme.py`.
- Fix log filtering for existing entries: `log_viewer.py`.
- Add or refine loop-centric task detail display: `task_loop_panel.py` and `status_panel.py`.
- Adjust batch question UX or activity display: `question_panel.py`.

## Change Map
- Description single-box Markdown edit/preview UX: `description_panel.py`.
- Question flow modal launch and question-phase signal bridging: `question_panel.py`.
- Provider/model selector behavior: `llm_selector_panel.py`.
- Run configuration options and working directory selection: `config_panel.py`.
- Log rendering, filtering, and scroll behavior: `log_viewer.py`.
- Phase/iteration display and task-percent progress bar: `status_panel.py`.
- Main-loop action + Markdown-rendered completed/incomplete task lists: `task_loop_panel.py`.
