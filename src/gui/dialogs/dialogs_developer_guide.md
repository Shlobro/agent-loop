# dialogs Developer Guide

## Purpose
Contains modal dialogs used by the GUI for user approvals and confirmations.

## Contents
- `git_approval_dialog.py`: Modal dialog asking whether to push committed changes and optionally remember the choice.
- `review_settings_dialog.py`: Modal dialog for selecting which review types/reviewers run during the debug/review loop.
- `__init__.py`: Module marker.

## Key Interactions
`GitApprovalDialog.get_approval()` returns `(should_push, remember)` for the caller.

## Change Map
- Update git approval UI copy or layout: `git_approval_dialog.py`.
