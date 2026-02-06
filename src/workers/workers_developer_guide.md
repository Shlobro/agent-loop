# workers Developer Guide

## Purpose
Implements QRunnable workers that execute each workflow phase asynchronously and emit Qt signals back to the GUI.

## Contents
- `signals.py`: `WorkerSignals` used by all workers (status, progress, logs, phase outputs).
- `base_worker.py`: Common QRunnable base with cancel/pause support and error handling.
- `llm_worker.py`: Subprocess runner for LLM CLIs with streaming output, timeouts, full prompt logging, optional output-file capture (also emitted to the log) for providers like Codex, and a live Windows terminal window per LLM run that shows the exact command plus streamed output. The popup remains open after completion so developers can inspect output and close it manually.
- `question_worker.py`: Generates a batch of clarifying questions from the LLM and loads them exclusively from `questions.json` (single attempt; no stdout parsing or fallback prompts). Also contains the worker that rewrites Q&A into `product-description.md` before additional question batches and only trusts file-based output from `product-description.md` (stdout is ignored for rewrite content).
- `planning_worker.py`: Reads `product-description.md` (when available), prepares an empty `tasks.md`, and loads the task list after the LLM writes directly to it.
- `execution_worker.py`: Executes a single task iteration, injects a fresh workspace compliance report (one developer guide `.md` per folder with a root exception, read guide before editing, update ancestor guides, <=10 code files per folder with `.md` excluded, <=1000 lines per code file) into the prompt, and updates task state in `tasks.md`.
- `review_worker.py`: Runs review/fix cycles per selected review type (including UI/UX), adding workspace compliance guidance (the five workspace rules) to the fixer prompt with a fresh compliance scan each cycle.
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
