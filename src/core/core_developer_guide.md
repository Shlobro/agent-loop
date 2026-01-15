# core Developer Guide

## Purpose
Implements the workflow state machine, persistence, file/session I/O, and shared exceptions.

## Contents
- `state_machine.py`: `Phase`, `SubPhase`, `StateContext`, and transitions. Emits signals used by `MainWindow`.
- `file_manager.py`: Atomic read/write for `tasks.md`, `recent-changes.md`, `review.md`, and arbitrary files in the working directory.
- `session_manager.py`: Save/load workflow state to `session_state.json` for pause/resume.
- `project_settings.py`: `ProjectSettings` dataclass plus JSON load/save helpers.
- `question_prefetch_manager.py`: Manages single-question buffering and cancellation.
- `exceptions.py`: Core exception types shared by workers and UI.
- `__init__.py`: Module marker.

## Working-Directory Artifacts
`FileManager` owns the core artifacts:
- `tasks.md`, `recent-changes.md`, `review.md`, `description.md` (written in planning).
- `session_state.json` (managed by `SessionManager`).

## Key Interactions
- `MainWindow` owns the `StateMachine` and applies context updates for every phase.
- Workers call `FileManager` for workflow artifact I/O.
- `SessionManager` serializes `StateMachine.to_dict()` and restores with `from_dict()`.
- `QuestionPrefetchManager` starts `SingleQuestionWorker` instances to keep a small buffer of questions.

## When to Edit Core
- Add phases or transitions: `state_machine.py` (`Phase`, `SubPhase`, `TRANSITIONS`).
- Persist new context fields: `state_machine.py` (`StateContext`) and `session_manager.py`.
- Change how `tasks.md`/`recent-changes.md`/`review.md` are created or trimmed: `file_manager.py`.
- Add new configurable settings or defaults: `project_settings.py`.
- Modify question buffering or cancellation: `question_prefetch_manager.py`.

## Change Map
- Phase flow and pause/resume: `state_machine.py`, `session_manager.py`.
- Artifact limits (like recent-changes size): `file_manager.py`.
- Default review types or LLM config storage: `project_settings.py`, `state_machine.py`.
