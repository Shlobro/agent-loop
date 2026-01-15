# Repository Guidelines

## Project Structure & Module Organization
`main.py` is the PySide6 GUI entry point. Core workflow logic lives in `src/core/` (state machine, file/session handling). UI code is in `src/gui/` with `widgets/` and `dialogs/` for reusable panels. LLM integration and prompt templates are in `src/llm/`, and async execution uses QRunnable workers in `src/workers/`. Utility parsers live in `src/utils/`. Runtime artifacts such as `tasks.md`, `recent-changes.md`, and `review.md` are created in the working directory during runs.

## Build, Test, and Development Commands
Use a local venv and install dependencies:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```
LLM CLIs must be available on PATH if you use the built-in providers:
`claude --dangerously-skip-permissions` (one-time), `gemini "<prompt>" --yolo`, or `codex exec --full-auto "<prompt>"`.

## Coding Style & Naming Conventions
Follow the existing Python style: 4-space indentation, module-level docstrings, and type hints on public APIs. Use `snake_case` for functions/modules, `PascalCase` for classes, and `UPPER_CASE` for constants and enums. Keep Qt signal definitions centralized (see `src/workers/signals.py`) and emit them from worker classes.

## Testing Guidelines
There is no automated test suite in the repository yet. If you add tests, prefer `pytest` with `tests/` at the repo root and `test_*.py` naming. Focus on deterministic logic in `src/core/` and `src/llm/` first; avoid GUI-only tests unless necessary.

## Commit & Pull Request Guidelines
Git history uses short, sentence-style messages without scopes or prefixes (for example, `added the option to enter a remote for git`). Keep commits similarly concise and descriptive. For pull requests, include a brief summary, steps to run (`python main.py`), and screenshots for any UI changes. Call out any new LLM provider setup requirements or dependency additions.
