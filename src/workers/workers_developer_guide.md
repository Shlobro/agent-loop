# workers Developer Guide

## Purpose
Implements QRunnable workers that execute each workflow phase asynchronously and emit Qt signals back to the GUI.

## Contents
- `signals.py`: `WorkerSignals` used by all workers (status, progress, logs, phase outputs).
- `base_worker.py`: Common QRunnable base with cancel/pause support and error handling.
- `llm_worker.py`: Subprocess runner for LLM CLIs with streaming output and timeouts.
- `question_worker.py`: Generates batch questions or a single question from the LLM and writes JSON files.
- `planning_worker.py`: Generates `description.md` and `tasks.md`.
- `execution_worker.py`: Executes a single task iteration and updates task state in `tasks.md`.
- `review_worker.py`: Runs review/fix cycles per selected review type and iterations using `review.md`.
- `git_worker.py`: LLM-driven git add/commit and optional push.
- `__init__.py`: Module marker.

## Key Interactions
- `MainWindow` creates workers, connects `WorkerSignals`, and schedules them on a `QThreadPool`.
- `LLMWorker` is reused by phase-specific workers to invoke providers from `llm/`.
- `FileManager` in `core/` is used by workers to read/write workflow artifacts.

## When to Edit Workers
- Add new signal payloads: `signals.py` and the emitting worker.
- Change cancellation or pause semantics: `base_worker.py`.
- Adjust LLM process timeouts or stdin/argv handling: `llm_worker.py`.
- Update question generation flow or JSON file output: `question_worker.py`.
- Modify task planning structure or description generation: `planning_worker.py`.
- Change how tasks are chosen or marked complete: `execution_worker.py`.
- Change review iteration rules or early-exit logic: `review_worker.py`.
- Alter git commit/push behavior: `git_worker.py`.

## Change Map
- Signals and threading basics: `signals.py`, `base_worker.py`.
- LLM invocation and error handling: `llm_worker.py`.
- Phase-specific logic: `question_worker.py`, `planning_worker.py`, `execution_worker.py`, `review_worker.py`, `git_worker.py`.
