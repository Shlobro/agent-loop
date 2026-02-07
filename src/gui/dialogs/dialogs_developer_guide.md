# dialogs Developer Guide

## Purpose
Contains modal dialogs used by the GUI for user approvals and confirmations.

## Contents
- `configuration_settings_dialog.py`: Modal dialog for execution and project configuration (opened from `Settings -> Configuration Settings`).
- `git_approval_dialog.py`: Modal dialog asking whether to push committed changes and optionally remember the choice.
- `llm_settings_dialog.py`: Modal dialog for selecting provider/model per workflow stage (opened from `Settings -> LLM Settings`).
- `question_answer_dialog.py`: Modal keyboard-first question window used during `Phase.AWAITING_ANSWERS`; supports Up/Down answer selection, Left/Right previous-next question, and Enter submit/advance (Enter on last question submits and closes). The dialog blocks manual close actions (`Esc`/window close) until the last answer is submitted.
- `review_settings_dialog.py`: Modal dialog for selecting which review types/reviewers run during the debug/review loop and whether the optional pre-review unit-test-update phase runs.
- `debug_settings_dialog.py`: Modal dialog for enabling/disabling debug step mode, choosing per-stage before/after pause points, toggling LLM terminal window popups, and showing/hiding the left logs panel.
- `startup_directory_dialog.py`: Startup-only modal dialog that requires selecting a valid working directory before the main window is shown, with recent-directory shortcuts.
- `__init__.py`: Module marker.

## Key Interactions
`GitApprovalDialog.get_approval()` returns `(should_push, remember)` for the caller.

## Change Map
- Update git approval UI copy or layout: `git_approval_dialog.py`.
- Update keyboard question-answer UX and modal visual style: `question_answer_dialog.py` (button variants/fade-in are shared via `../theme.py`).
