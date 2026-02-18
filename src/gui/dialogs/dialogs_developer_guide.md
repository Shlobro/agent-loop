# dialogs Developer Guide

## Purpose
Contains dialogs used by the GUI for user approvals, confirmations, and post-question flow decisions.

## Contents
- `configuration_settings_dialog.py`: Modal dialog for execution and project configuration (opened from `Settings -> Configuration Settings`).
- `git_approval_dialog.py`: Modal dialog asking whether to push committed changes and optionally remember the choice.
- `llm_settings_dialog.py`: Modal dialog for selecting provider/model per workflow stage (opened from `Settings -> LLM Settings`). Includes `Save Config File...` and `Load Config File...` actions for reusable stage mappings; closing the dialog applies current selections back to the main selector state.
- `question_answer_dialog.py`: Modal keyboard-first question window used during `Phase.AWAITING_ANSWERS`; supports Up/Down answer selection, Left/Right previous-next question, and Enter submit/advance (Enter on last question submits and closes). The dialog uses larger typography for question text and answer options to improve readability, and blocks manual close actions (`Esc`/window close) until the last answer is submitted.
- `question_flow_decision_dialog.py`: Non-modal post-rewrite decision dialog that appears after answers are folded into `product-description.md`. It keeps question flow paused until the user explicitly selects either `Ask More Questions` or `Start Main Loop`, while allowing description edits in the main window. The explanatory message is styled with larger text for clearer decision prompts.
- `review_settings_dialog.py`: Modal dialog split into two sections for UX clarity: `Pre-Review Preparation` (optional unit-test prep that runs once before the loop) and `Review Loop Types` (reviewers that run each iteration).
- `debug_settings_dialog.py`: Modal dialog for enabling/disabling debug step mode, choosing per-stage before/after pause points, toggling LLM terminal window popups, and showing/hiding the left logs panel.
- `startup_directory_dialog.py`: Working-directory picker dialog used both at startup and from `File -> Open Project...` at runtime. Requires selecting a valid working directory and includes recent-directory shortcuts.
- `error_recovery_dialog.py`: Modal dialog shown when workflow errors occur. Provides three recovery options: Retry Phase (re-run from start), Skip to Next (move to next iteration), and Send to LLM (automated error fixing with provider selection). Returns via signals (`retry_requested`, `skip_requested`, `send_to_llm_requested`). Blocks manual close to force user choice.
- `error_conclusion_dialog.py`: Modal dialog shown after LLM error fix attempt to display contents of `error-conclusion.md`. If empty (LLM failed), prompts user to try different LLM, retry manually, or skip. If has content (LLM succeeded), shows conclusion and allows retry with fixes, try different LLM, or skip. Returns via signals (`retry_requested`, `try_different_llm_requested`, `skip_requested`).
- `__init__.py`: Module marker.

## Key Interactions
`GitApprovalDialog.get_approval()` returns `(should_push, remember)` for the caller.

## Change Map
- Update git approval UI copy or layout: `git_approval_dialog.py`.
- Update keyboard question-answer UX and modal visual style: `question_answer_dialog.py` (button variants/fade-in are shared via `../theme.py`).
- Update post-rewrite branching behavior (`Ask More Questions` vs `Start Main Loop`): `question_flow_decision_dialog.py`.
