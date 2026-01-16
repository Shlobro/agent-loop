# gui Developer Guide

## Purpose
Implements the PySide6 UI layer. The main window orchestrates the workflow, connects signals, and coordinates worker threads.

## Contents
- `main_window.py`: Application controller and UI shell. Wires all panels, manages phase transitions, and dispatches workers.
- `widgets/`: Reusable UI panels (description, questions, logs, config, status, LLM selection).
- `dialogs/`: Modal dialogs (git approval).
- `__init__.py`: Module marker.

## Key Interactions
- `MainWindow` owns the `StateMachine`, `QuestionPrefetchManager`, and a `QThreadPool`.
- Worker results and log output are streamed back to UI via `WorkerSignals`.
- UI panels emit signals for user actions (start/pause/stop, question answers, settings changes).
- Review labels shown in UI/logs use `PromptTemplates.get_review_display_name`.

## MainWindow Responsibilities
- Validate inputs, read config, and seed `StateContext`.
- Schedule workers for each phase and route worker outputs.
- Update UI state (enable/disable panels, status bar, activity panel).
- Manage working directory artifacts via `FileManager`.
- Manage session save/resume through `SessionManager`.

## When to Edit GUI
- Start/pause/stop flow or phase routing: `main_window.py`.
- Enable LLM changes mid-run or add new UI actions: `main_window.py`, `widgets/llm_selector_panel.py`.
- Add new controls or settings (review types include UI/UX): `widgets/config_panel.py`.
- Fix log rendering/filtering: `widgets/log_viewer.py`.
- Show description/task progress in the UI: `widgets/description_panel.py`, `widgets/status_panel.py`, `main_window.py`.

## Change Map
- Workflow control or signal wiring: `main_window.py`.
- UI layout and component composition: `main_window.py`.
- Individual panel behavior: `widgets/`.
- User confirmation modals: `dialogs/`.
