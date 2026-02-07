# dialogs Developer Guide

## Purpose
Contains modal dialogs used by the GUI for user approvals and confirmations.

## Contents
- `git_approval_dialog.py`: Modal dialog asking whether to push committed changes and optionally remember the choice.
- `review_settings_dialog.py`: Modal dialog for selecting which review types/reviewers run during the debug/review loop and whether the optional pre-review unit-test-update phase runs.
- `debug_settings_dialog.py`: Modal dialog for enabling/disabling debug step mode, choosing per-stage before/after pause points, and toggling LLM terminal window popups.
- `startup_directory_dialog.py`: Startup-only modal dialog that requires selecting a valid working directory before the main window is shown, with recent-directory shortcuts.
- `__init__.py`: Module marker.

## Key Interactions
`GitApprovalDialog.get_approval()` returns `(should_push, remember)` for the caller.

## Change Map
- Update git approval UI copy or layout: `git_approval_dialog.py`.
