# core Developer Guide

## Purpose
Implements the workflow state machine, persistence, file/session I/O, and shared exceptions.

## Contents
- `state_machine.py`: `Phase`, `SubPhase`, `StateContext`, and transitions (includes UI/UX review sub-phases). Emits signals used by `MainWindow`.
- `file_manager.py`: Atomic read/write for `tasks.md`, `recent-changes.md`, `review.md`, `description.md`, governance prompt files (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`), and workspace rule compliance scans (one `.md` per folder excluding system/tooling dirs, <=10 files per folder, <=1000 lines per code file). Includes cache invalidation on working directory changes.
- `session_manager.py`: Save/load workflow state to `session_state.json` for pause/resume.
- `project_settings.py`: `ProjectSettings` dataclass plus JSON load/save helpers.
- `exceptions.py`: Core exception types shared by workers and UI.
- `__init__.py`: Module marker.

## Working-Directory Artifacts
`FileManager` owns the core artifacts:
- `tasks.md`, `recent-changes.md`, `review.md`, `description.md` (synced from UI and rewritten from Q&A before planning; overwritten in planning with the full spec).
- `session_state.json` (managed by `SessionManager`).

## Key Interactions
- `MainWindow` owns the `StateMachine` and applies context updates for every phase.
- Workers call `FileManager` for workflow artifact I/O.
- `SessionManager` serializes `StateMachine.to_dict()` and restores with `from_dict()`.

## When to Edit Core
- Add phases or transitions: `state_machine.py` (`Phase`, `SubPhase`, `TRANSITIONS`).
- Persist new context fields: `state_machine.py` (`StateContext`) and `session_manager.py`.
- Change how `tasks.md`/`recent-changes.md`/`review.md` are created or trimmed, or adjust workspace rule scanning: `file_manager.py`.
- Add new configurable settings or defaults: `project_settings.py`.

## Change Map
- Phase flow and pause/resume: `state_machine.py`, `session_manager.py`.
- Artifact limits (like recent-changes size): `file_manager.py`.
- Default review types or LLM config storage: `project_settings.py`, `state_machine.py`.
