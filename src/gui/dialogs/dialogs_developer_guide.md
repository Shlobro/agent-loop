# dialogs Developer Guide

## Purpose
Contains modal dialogs used by the GUI for user approvals and confirmations.

## Contents
- `git_approval_dialog.py`: Modal dialog asking whether to push committed changes and optionally remember the choice.
- `__init__.py`: Module marker.

## Key Interactions
`GitApprovalDialog.get_approval()` returns `(should_push, remember)` for the caller.

## Change Map
- Update git approval UI copy or layout: `git_approval_dialog.py`.
