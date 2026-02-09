# gui Developer Guide

## Purpose
Implements the PySide6 UI layer. The main window orchestrates the workflow, connects signals, and coordinates worker threads.

## Contents
- `main_window.py`: Application controller and UI shell. Wires panels, manages phase transitions, and delegates worker execution to mixins.
- `settings_mixin.py`: Settings handlers used by `MainWindow` (save/load project settings, configuration/LLM/review/debug settings dialog wiring, left panel tab visibility control for logs/description/tasks, and automatic per-working-directory settings sync under `.agentharness/project-settings.json`). UI defaults are all hidden left tabs unless a directory settings file enables them. Settings are automatically saved when the application closes to preserve UI state between sessions.
- `workflow_runner.py`: Worker execution mixin for planning, execution, review, and git phases.
- `theme.py`: Centralized Qt Fusion stylesheet plus helper utilities for button variants and fade-in animations. It defines the global typography scale (base font, inputs, group titles, buttons, hero labels, and list-item spacing) used across dialogs and widgets.
- `widgets/`: Reusable UI panels (description with Edit/Preview/Task List modes and automatic mode switching during iteration, hidden question-flow bridge, logs, config, status, LLM selection).
- `dialogs/`: Modal dialogs (git approval, review settings, debug settings, startup working-directory selection, keyboard-first question answering).
- `__init__.py`: Module marker.

## Key Interactions
- `MainWindow` owns the `StateMachine` and a `QThreadPool`, and mixes in worker handlers from `WorkflowRunnerMixin`.
- `main.py` shows `dialogs/startup_directory_dialog.py` before creating `MainWindow`; app startup now requires selecting a working directory and supports recent-directory shortcuts.
- After directory selection, `MainWindow` defaults to a minimalist two-column composition: optional left tab panel (hidden by default) and right chat panel (always visible). The left panel can contain up to 3 independently toggleable tabs (Logs, Description, Tasks) controlled via `View` menu. The status panel (top bar) is always visible and shows current phase, iteration count, sub-status details, and task-based progress. Workflow commands are exposed in the `Workflow` menu with shortcuts and menu bar icon buttons.
- To keep startup minimal while preserving discoverability, `MainWindow` also renders a floating circular start button (standard forward icon, gradient fill, soft shadow) that appears only when the app is idle and the description is non-empty; it triggers the same start path as `Workflow -> Start`.
- The menu bar includes workflow control icon buttons (Start/Play, Pause, Stop, Next Step) positioned in the top-right corner for quick access. These mirror the functionality of the Workflow menu items. Control buttons row has been removed - all workflow controls are accessible via menu bar icons and Workflow menu actions. IMPORTANT: The corner widget container (`menu_button_container`) must be stored as a member variable to prevent Qt from prematurely deleting it and its child buttons. Updates to menu buttons include RuntimeError exception handling to gracefully handle Qt object lifetime edge cases.
- `MainWindow` also controls debug-step gating for every LLM call through `Settings -> Debug Settings` and a `Next Step` button in the menu bar.
- The same workflow controls are always accessible from `Workflow` menu actions (`Start/Resume`, `Pause`, `Stop`, `Next Step`) and the menu bar icon buttons.
- Worker results and log output are streamed back to UI via `WorkerSignals`.
- `workflow_runner.py` handles git-phase completion defensively: if the git result payload is malformed or `tasks.md` cannot be read after commit, it logs recovery diagnostics, attempts to recreate required workflow files, and avoids silent loop stalls by transitioning to a controlled error state on unexpected exceptions.
- During `MAIN_EXECUTION`/`DEBUG_REVIEW`/`GIT_OPERATIONS` (and `COMPLETED`), `MainWindow` automatically switches `widgets/description_panel.py` to Task List mode, which replaces the main content area with task progress information: current action, completed/incomplete counts, and tabbed Markdown-rendered task lists (All/Completed/Incomplete filters) sourced from `tasks.md`. The view mode controls (Preview/Task List buttons) are automatically shown during these phases.
- The top-right status-bar progress percentage is driven by task completion ratio from `tasks.md`, not by max-iteration count.
- UI panels emit signals for user actions (start/pause/stop, batch question answers, settings changes); question answering is handled in a modal keyboard-driven window that cannot be dismissed until final submission, while `MainWindow` keeps `product-description.md` synced with the description widget, force-syncs the current GUI description to `product-description.md` before each question batch and before task planning, initializes an empty `questions.json` before each question batch, rewrites only the current submitted Q&A batch into `product-description.md` right after answers are submitted using the dedicated `description_molding` stage, then updates the description widget from `product-description.md` only for that rewrite step, clears stored Q&A context so the rewritten description becomes the new baseline, and keeps configuration/LLM settings live-editable so updates apply to upcoming phases and iterations. After each rewrite, `question_panel.py` opens a non-modal decision dialog so the user can continue editing description text before explicitly choosing either another question batch or task planning.
- `MainWindow` drives chat UX lifecycle hooks: it always appends user chat entries (including first-message description initialization), maps phase/status updates into friendly rotating activity messages (question generation, planning, execution, unit-test prep, review, fix, git, and client-message handling), clears activity when the workflow is no longer actively working, and posts one-line bot completion messages for key milestones (for example when questions are ready).
- `MainWindow.on_working_dir_changed` updates `StateContext.working_directory` immediately when directory selection changes, so chat-triggered workers and pre-start actions use the selected project path.
- `MainWindow` initializes working-directory artifacts as soon as a valid directory is active (including the startup default path), including pre-creating `review/<type>.md` files for all active review types.
- When a user switches to a working directory that already contains incomplete checklist items in `tasks.md`, `MainWindow` prompts: "There are incomplete tasks in this project. Would you like to complete them?" If accepted, a second dialog prompts for the number of iterations to run. Upon confirmation, the workflow automatically starts and skips question/planning to resume directly in main execution against the existing tasks. This same two-step prompt (incomplete tasks confirmation + iteration count) also appears at startup if the default working directory contains incomplete tasks, and the workflow auto-starts after the iteration count is confirmed.
- A "Resume Tasks" button appears in the status panel when the app is in `IDLE` or `COMPLETED` phase and there are incomplete tasks in `tasks.md`. Clicking this button prompts for iteration count, then jumps directly into main execution for the incomplete tasks.
- When max iterations are reached but incomplete tasks remain, a popup dialog appears with a system beep, asking "x/x iterations complete. There are still tasks incomplete. Would you like to keep going?" with an input box to specify additional iterations. If the user accepts, the max iteration limit is increased and execution continues; otherwise, the workflow transitions to `COMPLETED`.
- `ConfigPanel` performs git repository bootstrap as soon as the working directory is set (including app startup default directory) and is rechecked immediately before task planning starts from the question flow: it ensures the directory is a git repo and applies configured `origin` remote URL.
- `LLMSelectorPanel` seeds default provider/model values per stage at UI setup (including `description_molding` and `unit_test_prep`); the selectors are edited from `Settings -> LLM Settings`, while `MainWindow` stores values in `StateContext.llm_config` and keeps them synced during execution. The stages are displayed in execution order: unit test prep is shown before reviewer and fixer to reflect that it runs first in the review phase.
- Review labels shown in UI/logs use `PromptTemplates.get_review_display_name`.

## MainWindow Responsibilities
- Validate inputs, read config, and seed `StateContext`.
- Schedule workers for each phase and route worker outputs.
- Update UI state (enable/disable panels, status bar, activity panel).
- Manage working directory artifacts via `FileManager`.
- Manage session save/resume through `SessionManager`.
- Expose menu actions including `Settings -> LLM Settings` for stage provider/model choices.
- Expose menu actions including `Settings -> Configuration Settings` for execution controls and working directory/git remote.
- Expose menu actions including `Settings -> Review Settings`, which opens a dialog with separate sections for one-time pre-review unit-test prep and per-iteration review-loop type selection.
- Expose menu actions including `Settings -> Debug Settings` (which also controls left logs-panel visibility).
- Expose menu actions for `Workflow` (run controls) and `View` (left panel tab toggles) to preserve a minimalist default layout. The View menu provides 3 toggles: Show Logs (left tab), Show Description (left tab), and Show Tasks (left tab). All tabs default to hidden. The left panel only appears when at least one tab is enabled. The right column always contains only the chat panel, never showing description or tasks above it. The status panel is always visible at the top of the window.

## When to Edit GUI
- Start/pause/stop flow or phase routing: `main_window.py`.
- Worker execution flow (planning/execution/review/git): `workflow_runner.py`.
- Enable or refine mid-run LLM/config changes: `main_window.py`, `widgets/llm_selector_panel.py`, `widgets/config_panel.py`.
- Add new controls or settings (including review type selection via settings dropdown): `widgets/config_panel.py`, `dialogs/review_settings_dialog.py`.
- Fix log rendering/filtering: `widgets/log_viewer.py`.
- Show description (Edit/Preview/Task List modes with automatic mode switching) and task progress/list rendering in the UI: `widgets/description_panel.py`, `widgets/status_panel.py`, `main_window.py`.

## Change Map
- Workflow control or signal wiring: `main_window.py`.
- UI layout and component composition: `main_window.py`.
- Global visual style, palette, and simple motion: `theme.py`.
- Individual panel behavior: `widgets/`.
- User confirmation modals: `dialogs/`.
