# core Developer Guide

## Purpose
Implements the workflow state machine, persistence, file/session I/O, and shared exceptions.

## Contents
- `state_machine.py`: `Phase`, `SubPhase`, `StateContext`, and transitions (includes UI/UX review sub-phases). Emits signals used by `MainWindow`.
- `debug_settings.py`: Shared debug-stage identifiers, labels, and breakpoint normalization/default helpers. Defaults pause **before** every stage LLM call when debug mode is on (after-call pauses default off).
- `file_manager.py`: Atomic read/write for `tasks.md`, `recent-changes.md`, `review/` artifacts (one file per review type), `product-description.md`, git commit-message artifact (`.agentharness/git-commit-message.txt`), and governance prompt files (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`).
- `session_manager.py`: Save/load workflow state to `session_state.json` for pause/resume.
- `project_settings.py`: `ProjectSettings` dataclass plus JSON load/save helpers (includes review-type selection, optional pre-review unit-test-update toggle persistence, and left logs-panel visibility), including per-working-directory settings at `.agentharness/project-settings.json`. The default for `show_logs_panel` is `False` (left logs hidden unless enabled in settings).
- `error_context.py`: `ErrorInfo` dataclass for capturing complete error state including phase, traceback, recent logs, and state snapshot for recovery operations. Also contains `ErrorRecoveryTracker` to prevent infinite retry loops.
- `exceptions.py`: Core exception types shared by workers and UI.
- `__init__.py`: Module marker.

## Working-Directory Artifacts
`FileManager` owns the core artifacts:
- `tasks.md`, `recent-changes.md`, `review/` (per-review-type files such as `review/general.md`), and `product-description.md` (synced from UI and rewritten for planning after Q&A).
- `.agentharness/git-commit-message.txt` (created at startup by `ensure_files_exist()` as the git-ops LLM output target).
- `session_state.json` (managed by `SessionManager`).

## Key Interactions
- `MainWindow` owns the `StateMachine` and applies context updates for every phase.
- Workers call `FileManager` for workflow artifact I/O.
- `SessionManager` serializes `StateMachine.to_dict()` and restores with `from_dict()`.
- Default stage LLM config is seeded in `StateContext.llm_config` (including `description_molding` for the post-Q&A rewrite and `unit_test_prep` for the pre-review unit-test phase) and is replaced by the current UI selection at workflow start.
- Debug step config also lives in `StateContext` (`debug_mode_enabled`, per-stage `debug_breakpoints`, `show_llm_terminals`) so pause points and terminal visibility can be saved/loaded and restored from sessions.

## When to Edit Core
- Add phases or transitions: `state_machine.py` (`Phase`, `SubPhase`, `TRANSITIONS`).
- Persist new context fields: `state_machine.py` (`StateContext`) and `session_manager.py`.
- Change how `tasks.md`/`recent-changes.md`/review artifacts are created or trimmed: `file_manager.py`.
- Add new configurable settings or defaults: `project_settings.py`.
- Add or rename debug pause stages: `debug_settings.py` and the corresponding worker `debug_stage` values in `workers/`.

## Change Map
- Phase flow and pause/resume: `state_machine.py`, `session_manager.py`.
- Artifact limits (like recent-changes size): `file_manager.py`.
- Default review types, pre-review unit-test-update defaults, or LLM config storage: `project_settings.py`, `state_machine.py`.
