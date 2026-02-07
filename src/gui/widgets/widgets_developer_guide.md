# widgets Developer Guide

## Purpose
Reusable PySide6 panels used by `MainWindow` to assemble the UI.

## Contents
- `description_panel.py`: Project description input and read-only handling; changes are synced to `product-description.md` by `MainWindow`.
- `question_panel.py`: Single-question navigation for batch questions, answer capture, and live activity status display; enables submit once all questions are answered, shows an updating state after submission, and unlocks Generate More and Start Planning after the description rewrite completes.
- `llm_selector_panel.py`: Provider/model selection per workflow stage from the LLM registry, including built-in default stage assignments.
- `config_panel.py`: Execution settings (iterations, questions, working directory, git settings), stored review-type selections, and the optional pre-review unit-test-update toggle used by the review settings dialog.
- `log_viewer.py`: Color-coded log viewer with filtering and auto-scroll.
- `status_panel.py`: Top-line workflow status and progress bar.
- `__init__.py`: Module marker.

## Key Interactions
- `LLMSelectorPanel` queries `LLMProviderRegistry` to populate providers/models and then applies stage defaults:
- Question generation: Gemini + `gemini-3-pro-preview`
- Description molding: Gemini + `gemini-3-pro-preview`
- Task planning: Claude + `claude-opus-4-6`
- Coder: Claude + `claude-opus-4-6`
- Reviewer: Codex + `gpt-5.3-codex`
- Fixer: Codex + `gpt-5.3-codex`
- Git operations: Gemini + `gemini-3-pro-preview`
- `ConfigPanel` exposes `ExecutionConfig`; review type selections are edited through the main menu action `Settings -> Review Settings` and include all active review categories (General, Architecture, Efficiency, Error Handling, Safety, Testing, Documentation, UI/UX). The same dialog also controls whether the optional pre-review unit-test-update pass runs.
- `ConfigPanel` performs early git bootstrap for the selected working directory: checks whether the directory is already a git repo, runs `git init` when needed, shows a user-facing install notice if git commands are unavailable/fail, and configures `origin` when a remote URL is set.
- `QuestionPanel` emits signals for submitted batch answers, generating another batch, or start planning.
- `LogViewer` listens to worker log and LLM output signals from `MainWindow`.

## When to Edit Widgets
- Add or adjust review selection behavior: `config_panel.py` and `../dialogs/review_settings_dialog.py`.
- Change per-stage LLM selector behavior or enable runtime edits: `llm_selector_panel.py`.
- Fix log filtering for existing entries: `log_viewer.py`.
- Add task checklist/progress display: `status_panel.py` or a new widget in this folder.
- Adjust batch question UX or activity display: `question_panel.py`.

## Change Map
- Description input UX: `description_panel.py`.
- Question flow, answer capture, and live-status view: `question_panel.py`.
- Provider/model selector behavior: `llm_selector_panel.py`.
- Run configuration options and working directory selection: `config_panel.py`.
- Log rendering, filtering, and scroll behavior: `log_viewer.py`.
- Phase/iteration display and progress bar: `status_panel.py`.
