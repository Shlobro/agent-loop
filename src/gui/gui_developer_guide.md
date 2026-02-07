# gui Developer Guide

## Purpose
Implements the PySide6 UI layer. The main window orchestrates the workflow, connects signals, and coordinates worker threads.

## Contents
- `main_window.py`: Application controller and UI shell. Wires panels, manages phase transitions, and delegates worker execution to mixins.
- `settings_mixin.py`: Settings handlers used by `MainWindow` (save/load project settings and debug settings dialog wiring).
- `workflow_runner.py`: Worker execution mixin for planning, execution, review, and git phases.
- `widgets/`: Reusable UI panels (description, questions, logs, config, status, LLM selection).
- `dialogs/`: Modal dialogs (git approval, review settings).
- `dialogs/`: Modal dialogs (git approval, review settings, debug settings).
- `__init__.py`: Module marker.

## Key Interactions
- `MainWindow` owns the `StateMachine` and a `QThreadPool`, and mixes in worker handlers from `WorkflowRunnerMixin`.
- `MainWindow` also controls debug-step gating for every LLM call through `Settings -> Debug Settings` and a `Next Step` button in the main controls row.
- Worker results and log output are streamed back to UI via `WorkerSignals`.
- UI panels emit signals for user actions (start/pause/stop, batch question answers, settings changes); `MainWindow` keeps `product-description.md` synced with the description widget, force-syncs the current GUI description to `product-description.md` before each question batch and before task planning, initializes an empty `questions.json` before each question batch, rewrites only the current submitted Q&A batch into `product-description.md` right after answers are submitted using the dedicated `description_molding` stage, then updates the description widget from `product-description.md` only for that rewrite step, clears stored Q&A context so the rewritten description becomes the new baseline, unlocks description editing after the rewrite completes, and only then enables Generate More/Start Planning.
- `MainWindow` initializes working-directory artifacts as soon as a valid directory is active (including the startup default path), including pre-creating `review/<type>.md` files for all review types.
- `ConfigPanel` now performs git repository bootstrap as soon as the working directory is set (including app startup default directory): it ensures the directory is a git repo and applies configured `origin` remote URL.
- `LLMSelectorPanel` seeds default provider/model values per stage at UI setup (including `description_molding`); `MainWindow` reads that config on Start and stores it in `StateContext.llm_config`.
- Review labels shown in UI/logs use `PromptTemplates.get_review_display_name`.

## MainWindow Responsibilities
- Validate inputs, read config, and seed `StateContext`.
- Schedule workers for each phase and route worker outputs.
- Update UI state (enable/disable panels, status bar, activity panel).
- Manage working directory artifacts via `FileManager`.
- Manage session save/resume through `SessionManager`.
- Expose menu actions including `Settings -> Review Settings`, which opens the review selection dialog.
- Expose menu actions including `Settings -> Review Settings` and `Settings -> Debug Settings`.

## When to Edit GUI
- Start/pause/stop flow or phase routing: `main_window.py`.
- Worker execution flow (planning/execution/review/git): `workflow_runner.py`.
- Enable LLM changes mid-run or add new UI actions: `main_window.py`, `widgets/llm_selector_panel.py`.
- Add new controls or settings (including review type selection via settings dropdown): `widgets/config_panel.py`, `dialogs/review_settings_dialog.py`.
- Fix log rendering/filtering: `widgets/log_viewer.py`.
- Show description/task progress in the UI: `widgets/description_panel.py`, `widgets/status_panel.py`, `main_window.py`.

## Change Map
- Workflow control or signal wiring: `main_window.py`.
- UI layout and component composition: `main_window.py`.
- Individual panel behavior: `widgets/`.
- User confirmation modals: `dialogs/`.
