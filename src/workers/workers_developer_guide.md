# workers Developer Guide

## Purpose
Implements QRunnable workers that execute each workflow phase asynchronously and emit Qt signals back to the GUI.

## Contents
- `signals.py`: `WorkerSignals` used by all workers (status, progress, logs, phase outputs).
- `base_worker.py`: Common QRunnable base with cancel/pause support and error handling.
- `llm_worker.py`: Subprocess runner for LLM CLIs with streaming output, timeouts, full prompt logging, optional output-file capture (also emitted to the log), per-stage debug gates before/after each LLM call, and an optional live Windows terminal window per run that can be turned on/off from debug settings. Default LLM timeout is 600 seconds, retry delay is 4 seconds, output-thread join wait is 10 seconds, and cancellation graceful-wait timeout is 4 seconds. It validates the configured working directory before spawning subprocesses and falls back to the app process directory when the configured path is invalid. Takes a `provider` object (instance of `BaseLLMProvider`) obtained via `LLMProviderRegistry.get(provider_name)`, not a provider_name string.
- `question_worker.py`: Generates a batch of clarifying questions from the LLM and loads them exclusively from `questions.json` (single attempt; no stdout parsing or fallback prompts). Also contains the worker that rewrites Q&A into `product-description.md` before additional question batches and only trusts file-based output from `product-description.md` (stdout is ignored for rewrite content). Default providers are codex for question generation and claude for description rewrite when a caller does not pass explicit stage config.
- `planning_worker.py`: Prepares an empty `tasks.md` and loads the task list after the planning LLM writes it, then runs a research pass (selected `research` provider/model writes `research.md` using `product-description.md` plus `tasks.md`). Default research provider is claude when no explicit value is passed.
- `execution_worker.py`: Executes a configurable number of tasks per iteration (controlled by `tasks_per_iteration`) and updates task state in `tasks.md`. Uses a 1200-second LLM timeout for execution calls. Worker results include the concrete task titles completed in that iteration so the GUI can post user-facing completion summaries in chat.
- `review_worker.py`: Orchestrates the review phase in this order: (1) optional unit test prep pass (runs FIRST, uses `git diff` and may add/edit tests), (2) review/fix cycles per selected review type (including UI/UX). Initializes `review/` with empty files for every review type, reads findings from the current review file, skips fixer when that file is empty, truncates the same file after each completed fix cycle, and supports live updates of review iteration limits plus reviewer/fixer/unit-test-prep model selections between cycles. Unit-test-prep fallback defaults are codex + `gpt-5.3-codex`.
- `git_worker.py`: Hybrid git phase where code captures `git status --porcelain` and `git diff` and injects them into the LLM commit-message prompt, the LLM writes only a commit message file (`.agentharness/git-commit-message.txt`), then code performs `git add`, `git commit`, and optional `git push`, and truncates the commit-message file after a successful commit.
- `error_fix_worker.py`: Worker that sends error context to an LLM for automated analysis and fixing. Uses specialized error fix prompt template and runs after user selects "Send to LLM" option in error recovery dialog.
- `chat_to_description_worker.py`: Worker for LLM-driven initialization/update of `product-description.md`. The current first-message flow in `MainWindow` now saves the first message directly before clarifying questions, so this worker is available for explicit LLM-based description transforms rather than that default path.
- `client_message_worker.py`: Processes client messages during workflow execution. Supports checkbox-based control (update_description, add_tasks, provide_answer) to explicitly direct the LLM's behavior, or a no-checkbox headless wrapper mode that tells the LLM user-visible responses must be written to `answer.md` and includes the user message. Uses specialized prompts based on checkbox combinations (see CHECKBOX_PROMPTS.md). Changes to description and tasks are detected in the workflow_runner to display appropriate status messages in the chat panel.
- `__init__.py`: Module marker.

## Key Interactions
- `MainWindow` creates workers, connects `WorkerSignals`, and schedules them on a `QThreadPool`.
- `MainWindow` can pass live runtime settings into `ReviewWorker` so debug/review iterations and reviewer/fixer/unit-test-prep choices can be changed while the loop is running.
- `MainWindow` injects debug gate behavior through `LLMWorker.set_debug_gate_callback` and `LLMWorker.set_show_live_terminal_windows`.
- `LLMWorker` is reused by phase-specific workers to invoke providers from `llm/`.
- `FileManager` in `core/` is used by workers to read/write workflow artifacts.
- `GitWorker` uses subprocess git commands for staging/committing/pushing, and only delegates commit-message drafting to the selected LLM provider.

## When to Edit Workers
- Add new signal payloads: `signals.py` and the emitting worker.
- Change cancellation or pause semantics: `base_worker.py`.
- Adjust LLM process timeouts or stdin/argv handling: `llm_worker.py`.
- Update question generation flow or JSON file output: `question_worker.py`.
- Modify task planning structure or description generation: `planning_worker.py`.
- Change how tasks are chosen or marked complete: `execution_worker.py`.
- Change pre-review unit-test-update behavior, review iteration rules, per-type review file behavior, or early-exit logic: `review_worker.py`.
- Alter git commit/push behavior: `git_worker.py`.

## Change Map
- Signals and threading basics: `signals.py`, `base_worker.py`.
- LLM invocation and error handling: `llm_worker.py`.
- Phase-specific logic: `question_worker.py`, `planning_worker.py`, `execution_worker.py`, `review_worker.py`, `git_worker.py`.
