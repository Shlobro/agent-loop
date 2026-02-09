# widgets Developer Guide

## Purpose
Reusable PySide6 panels used by `MainWindow` to assemble the UI.

## Contents
- `description_panel.py`: Multi-mode project description surface supporting three view modes: Edit (default), Preview (Markdown rendering), and Task List (shows current action, completed/incomplete task counts and lists during iteration). View controls can be shown via `View` menu in `MainWindow`; changes are synced to `product-description.md`. During main loop execution, automatically switches to Task List mode.
- `question_panel.py`: Hidden signal bridge for question flow. It opens `dialogs/question_answer_dialog.py` as a modal window when questions are ready, emits submitted Q&A pairs, and then opens `dialogs/question_flow_decision_dialog.py` after rewrite so the user explicitly chooses `Ask More Questions` or `Start Main Loop`.
- `llm_selector_panel.py`: Provider/model selection per workflow stage from the LLM registry, including built-in default stage assignments; hosted by `Settings -> LLM Settings` and used as the canonical in-memory stage config for the run. Stages are displayed in execution order, with Unit Test Prep shown before Reviewer and Fixer to reflect that it runs first in the review phase. Includes Client Message Handler stage for processing user messages during workflow execution.
- `config_panel.py`: Execution settings (iterations, tasks per iteration, questions, working directory, git settings), stored review-type selections, and the optional pre-review unit-test-update toggle used by the review settings dialog; hosted by `Settings -> Configuration Settings`, while values stay live-editable during execution.
- `log_viewer.py`: Color-coded log viewer with filtering and auto-scroll; uses an enlarged monospace font for clearer streaming output.
- `status_panel.py`: Top-line workflow status, iteration label, top-right progress bar, and a "Resume Tasks" button that appears when incomplete tasks exist and the workflow is idle or completed; progress is task-list based (`completed tasks / total tasks`) during loop execution.
- `chat_panel.py`: Chat interface for sending messages to LLM during workflow execution. Messages queue and are processed at iteration boundaries after git operations. Shows message history with status indicators and LLM answers. Hidden by default; toggle via `View -> Show Chat Panel`.
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
- `DescriptionPanel` uses a `QStackedWidget` to manage three view modes: Edit mode (editable text), Preview mode (Markdown rendering via `QTextBrowser.setMarkdown(...)`), and Task List mode (shows current agent action plus completed/incomplete task counts and Markdown-rendered task lists). The explicit `Edit`/`Preview`/`Task List` controls are hidden by default and can be enabled from the `View` menu. During main loop phases, the panel automatically switches to Task List mode and shows controls.
- `LogViewer` listens to worker log and LLM output signals from `MainWindow`.

## When to Edit Widgets
- Add or adjust review selection behavior: `config_panel.py` and `../dialogs/review_settings_dialog.py`.
- Change per-stage LLM selector behavior or enable runtime edits: `llm_selector_panel.py`.
- Adjust visual tone for logs/status/description surfaces while preserving behavior: `description_panel.py`, `log_viewer.py`, `status_panel.py`, and shared styles in `../theme.py`.
- Fix log filtering for existing entries: `log_viewer.py`.
- Add or refine task list display, view mode behavior, or product description editing: `description_panel.py` and `status_panel.py`.
- Adjust batch question UX or activity display: `question_panel.py`.

## ChatPanel
Location: `chat_panel.py`

Chat interface for sending messages to LLM during workflow execution or when idle.

Features:
- Message input area with send button
- Message history showing status (queued/processing/completed)
- Displays LLM answers inline with blue background
- Enabled whenever a working directory is active (except during ERROR/CANCELLED phases)
- Messages queue during execution and process at iteration boundaries
- Messages process immediately when workflow is idle
- Hidden by default (show via View menu)

Signals:
- `message_sent(str)` - emitted when user sends a message

Key methods:
- `add_message(id, content, status)` - add message to history
- `update_message_status(id, status)` - update message status
- `add_answer(id, answer)` - add LLM answer to message
- `set_input_enabled(bool)` - enable/disable input

## Change Map
- Description multi-mode UX (Edit/Preview/Task List) with automatic mode switching during iteration: `description_panel.py`.
- Question flow modal launch and question-phase signal bridging: `question_panel.py`.
- Provider/model selector behavior: `llm_selector_panel.py`.
- Run configuration options and working directory selection: `config_panel.py`.
- Log rendering, filtering, and scroll behavior: `log_viewer.py`.
- Phase/iteration display, task-percent progress bar, and resume button for incomplete tasks: `status_panel.py`.
- Client messaging interface and message history display: `chat_panel.py`.
