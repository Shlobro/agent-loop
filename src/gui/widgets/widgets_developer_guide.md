# widgets Developer Guide

## Purpose
Reusable PySide6 panels used by `MainWindow` to assemble the UI.

## Contents
- `description_panel.py`: Project description input and read-only handling.
- `question_panel.py`: Single-question workflow UI, answer capture, and live activity status display.
- `llm_selector_panel.py`: Provider/model selection per workflow stage from the LLM registry.
- `config_panel.py`: Execution settings (iterations, questions, review types, working directory, git settings).
- `log_viewer.py`: Color-coded log viewer with filtering and auto-scroll.
- `status_panel.py`: Top-line workflow status and progress bar.
- `__init__.py`: Module marker.

## Key Interactions
- `LLMSelectorPanel` queries `LLMProviderRegistry` to populate providers/models.
- `ConfigPanel` exposes `ExecutionConfig` and review type selections from `PromptTemplates`.
- `QuestionPanel` emits signals for submitted answers, more questions, or start planning.
- `LogViewer` listens to worker log and LLM output signals from `MainWindow`.

## When to Edit Widgets
- Add a new review type toggle or setting: `config_panel.py`.
- Change per-stage LLM selector behavior or enable runtime edits: `llm_selector_panel.py`.
- Fix log filtering for existing entries: `log_viewer.py`.
- Add task checklist/progress display: `status_panel.py` or a new widget in this folder.
- Adjust question flow UX or activity display: `question_panel.py`.

## Change Map
- Description input UX: `description_panel.py`.
- Question flow, answer capture, and live-status view: `question_panel.py`.
- Provider/model selector behavior: `llm_selector_panel.py`.
- Run configuration options and working directory selection: `config_panel.py`.
- Log rendering, filtering, and scroll behavior: `log_viewer.py`.
- Phase/iteration display and progress bar: `status_panel.py`.
