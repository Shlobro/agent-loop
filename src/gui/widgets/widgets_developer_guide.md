# widgets Developer Guide

## Purpose
Reusable PySide6 panels used by `MainWindow` to assemble the UI.

## Contents
- `description_panel.py`: Task list panel located ONLY in the left tab widget (Tasks tab). Shows task progress with current action, completed/incomplete task counts, and tabbed task filtering (All/Completed/Incomplete). The panel no longer handles description preview - that's now in a separate QTextBrowser in the Description tab of the left panel. Description content is stored in MainWindow's `_description_content` variable. View mode controls are hidden since the panel is always in Task List mode when used in the left tab. The Tasks tab can be toggled via `View -> Show Tasks` in `MainWindow`.
- `question_panel.py`: Hidden signal bridge for question flow. It opens `dialogs/question_answer_dialog.py` as a modal window when questions are ready, emits submitted Q&A pairs, and then opens `dialogs/question_flow_decision_dialog.py` after rewrite so the user explicitly chooses `Ask More Questions` or `Start Main Loop`.
- `llm_selector_panel.py`: Provider/model selection per workflow stage from the LLM registry, including built-in default stage assignments; hosted by `Settings -> LLM Settings` and used as the canonical in-memory stage config for the run. Stages are displayed in execution order, including a dedicated `Research (after task planning)` stage, with Unit Test Prep shown before Reviewer and Fixer to reflect that it runs first in the review phase. Includes Client Message Handler stage for processing user messages during workflow execution.
- `config_panel.py`: Execution settings (iterations, tasks per iteration, questions, working directory, git settings), stored review-type selections, and the optional pre-review unit-test-update toggle used by the review settings dialog; hosted by `Settings -> Configuration Settings`, while values stay live-editable during execution.
- `log_viewer.py`: Color-coded log viewer with filtering and auto-scroll; uses an enlarged monospace font for clearer streaming output.
- `status_panel.py`: Top-line workflow status, iteration label, top-right progress bar, and a "Resume Tasks" button that appears when incomplete tasks exist and the workflow is idle or completed; progress is task-list based but phase-weighted during active loop execution so newly completed tasks earn partial progress in execution/review and reach full credit after git completes.
- `chat_panel.py`: Chat interface for initializing and updating product description, plus sending messages to LLM during workflow execution. Includes 3 checkboxes to control LLM behavior: "Update description" (updates product-description.md), "Add tasks" (adds tasks to tasks.md), and "Provide answer in text" (writes response to answer.md). When description is empty, first message initializes `product-description.md` and auto-triggers question generation if max_questions > 0. When description exists, messages are processed based on checkbox selections (see CHECKBOX_PROMPTS.md for details). Placeholder text changes based on description state. Messages queue during workflow and process at iteration boundaries. Uses chatbot-style user/bot bubbles with distinct colors, one-line status text, and an animated bot activity row (for example `Generating questions...`) during long-running bot actions. Supports `/clear` command to reset persisted history. Emits `clear_history_requested` (on `/clear`) and `bot_message_added(str)` (after each bot message) signals for `MainWindow` to update persistence. Call `load_history(messages)` to restore prior chat entries when switching projects, and `clear_display()` to wipe the display without persisting. Chat input shortcuts are `Enter` to send and `Shift+Enter` to insert a newline.
- `__init__.py`: Module marker.

## Key Interactions
- Widgets use the centralized stylesheet from `src/gui/theme.py`; prefer setting widget properties (for example `role="muted"`) instead of hardcoded inline colors.
- `LLMSelectorPanel` queries `LLMProviderRegistry` to populate providers/models and then applies stage defaults (in execution order):
- Question generation: Gemini + `gemini-3-pro-preview`
- Description molding: Gemini + `gemini-3-pro-preview`
- Task planning: Claude + `claude-opus-4-6`
- Research (after task planning): Gemini + `gemini-3-pro-preview`
- Coder: Claude + `claude-opus-4-6`
- Unit Test Prep (runs first in review): Gemini + `gemini-3-pro-preview`
- Reviewer: Codex + `gpt-5.3-codex`
- Fixer: Codex + `gpt-5.3-codex`
- Git operations: Gemini + `gemini-3-pro-preview`
- `ConfigPanel` exposes `ExecutionConfig`; review type selections are edited through the main menu action `Settings -> Review Settings` and include all active review categories (General, Architecture, Efficiency, Error Handling, Safety, Testing, Documentation, UI/UX). The same dialog also controls whether the optional pre-review unit-test-update pass runs.
- `ConfigPanel` keeps `Number of Questions`, `Max Main Iterations`, `Tasks Per Iteration`, and `Debug Loop Iterations` enabled during active runs so users can change upcoming question batches, loop limits, and tasks-per-iteration without stopping.
- `ConfigPanel` performs git bootstrap checks for the selected working directory both when the directory/remote changes and when planning starts: checks whether the directory is already a git repo, runs `git init` when needed, shows a user-facing install notice if git commands are unavailable/fail, and configures `origin` when a remote URL is set. Git subprocess calls in this panel use a 10-second timeout.
- `QuestionPanel` remains connected to `MainWindow` signal wiring but is not used as a visible section in the main layout.
- `DescriptionPanel` is now used ONLY for Task List mode and appears ONLY in the left tab widget (Tasks tab). It shows current agent action plus completed/incomplete task counts and tabbed Markdown-rendered task lists with All/Completed/Incomplete filters. The panel no longer has Preview mode - that's handled by a separate QTextBrowser in the Description tab. The explicit mode controls are always hidden since it's always in task list mode. Description content is managed in MainWindow via `_description_content` variable and helper methods `_get_description()` and `_set_description()`.
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
- Keyboard shortcuts: `Enter` sends, `Shift+Enter` inserts a newline
- 3 checkboxes to control LLM behavior:
  - "Update description" - updates product-description.md
  - "Add tasks" - adds tasks to tasks.md
  - "Provide answer in text" - writes response to answer.md
- Message history rendered as chatbot bubbles with distinct user and bot colors
- One-line message statuses (queued/processing/completed/failed) instead of log-style headers
- Displays LLM answers inline as bot bubbles, or shows file-update status messages when LLM updates files instead (e.g., "Updated product description", "Updated tasks")
- Animated bot activity indicator for in-progress background actions (for example question generation)
- Animated bot activity supports rotating friendly message options per workflow phase via `set_bot_activity_options(...)`, with a spinner rendered inline before the active message to signal progress.
- Enabled whenever a working directory is active (except during ERROR/CANCELLED phases)
- Messages queue during execution and process at iteration boundaries
- Messages process immediately when workflow is idle
- Checkboxes reset after each message is sent
- Always visible as the primary input method

Signals:
- `message_sent(str, bool, bool, bool)` - emitted when user sends a message with checkbox states (message, update_description, add_tasks, provide_answer)

Key methods:
- `add_message(id, content, status)` - add message to history
- `update_message_status(id, status)` - update message status
- `add_answer(id, answer)` - add LLM answer to message (also used for status messages like "Updated product description")
- `set_bot_activity(text)` / `clear_bot_activity()` - show/hide animated bot progress line
- `set_bot_activity_options(list[str])` - show one or more rotating activity messages with spinner animation
- `set_input_enabled(bool)` - enable/disable input and checkboxes

## Change Map
- Description multi-mode UX (Edit/Preview/Task List) with automatic mode switching during iteration: `description_panel.py`.
- Question flow modal launch and question-phase signal bridging: `question_panel.py`.
- Provider/model selector behavior: `llm_selector_panel.py`.
- Run configuration options and working directory selection: `config_panel.py`.
- Log rendering, filtering, and scroll behavior: `log_viewer.py`.
- Phase/iteration display, task-percent progress bar, and resume button for incomplete tasks: `status_panel.py`.
- Client messaging interface and message history display: `chat_panel.py`.
