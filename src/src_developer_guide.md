# src Developer Guide

## Purpose
Application source package for AgentHarness. This is where the workflow, UI, LLM integration, and parsing live.

## Folder Map
- `core/`: Phase state machine, session persistence, file I/O, and settings models.
- `gui/`: Main window orchestration and UI panels.
- `llm/`: Provider adapters and prompt templates for every phase.
- `utils/`: Parsers for LLM output and markdown task lists.
- `workers/`: QRunnable workers for each workflow phase (LLM runner logs full prompts, emits output-file content to the log, and on Windows opens a live terminal window for each LLM command; popups remain open after completion until closed manually).
- `__init__.py`: Package marker; importing `src.llm` registers providers.

## Phase-to-File Map
- Question generation: `workers/question_worker.py` (loads questions only from `questions.json` on a single LLM attempt; no stdout parsing or fallback prompts; rewrites Q&A into `product-description.md` before additional batches and reads that file back; rewrite content is accepted only from `product-description.md`, not stdout), `gui/widgets/question_panel.py` (single-question navigation and batch answers with submit-first gating and a post-submit updating state), `gui/main_window.py` (keeps `product-description.md` synced with the description widget, force-syncs GUI -> file before each question batch and before planning, initializes empty `questions.json` before each batch, rewrites only the currently submitted Q&A batch into `product-description.md` immediately after submission via the dedicated `description_molding` LLM selection, applies the rewrite result to the UI from `product-description.md` only in that rewrite step, clears stored Q&A/answers after rewrite so the rewritten description is the new baseline, unlocks description editing after the rewrite completes, and generates another question batch using the current GUI description), `llm/prompt_templates.py` (description-only question prompts that edit the empty `questions.json`, plus the Q&A-to-definition rewrite prompt that writes `product-description.md` via `PromptTemplates.format_definition_rewrite_prompt`).
- Task planning: `workers/planning_worker.py`, `llm/prompt_templates.py`, `core/file_manager.py` (planning prompts instruct the LLM to write directly to `tasks.md` based on the project description, preferring `product-description.md` when present).
- Main execution: `workers/execution_worker.py`, `llm/prompt_templates.py`, `core/file_manager.py`, `utils/markdown_parser.py` (includes workspace compliance checks: one developer guide `.md` per folder with a root exception, read guide before editing, update ancestor guides, <=10 code files per folder with `.md` excluded, <=1000 lines per code file, with a fresh scan each run).
- Review loop: `workers/review_worker.py`, `llm/prompt_templates.py`, `core/file_manager.py` (includes UI/UX review type).
- Review loop: `workers/review_worker.py`, `llm/prompt_templates.py`, `core/file_manager.py` (includes General, Unit Test, and UI/UX review types).
- Git operations: `workers/git_worker.py`, `llm/prompt_templates.py`.
- Pause/resume: `core/session_manager.py`, `core/state_machine.py`, `gui/main_window.py`.

## When to Edit What
- UI layout or control wiring: `gui/main_window.py` plus panels in `gui/widgets/` and `gui/dialogs/` (`Settings -> Review Settings` is wired in `main_window.py`).
- Worker execution routing in the GUI: `gui/workflow_runner.py`.
- Review label display formatting in logs/activity: `gui/main_window.py` (uses `PromptTemplates.get_review_display_name`).
- New runtime settings or persistence: `core/project_settings.py` and `gui/widgets/config_panel.py`.
- Add new LLM provider/model or CLI flags (including output-file capture and prompt transport mode): `llm/*_provider.py` plus `gui/widgets/llm_selector_panel.py`. Provider files hold the curated model ID lists shown in the UI; Claude and Gemini send prompts via stdin.
- Change default per-stage provider/model selections: `gui/widgets/llm_selector_panel.py` (UI defaults) and `core/state_machine.py` (`StateContext` fallback defaults).
- Task list parsing or mutation rules: `utils/markdown_parser.py`.
- Change phase sequencing or transitions: `core/state_machine.py` and `gui/main_window.py`.

## How It Fits
`main.py` instantiates `gui/main_window.py`. The GUI coordinates workers, which call into core utilities and LLM providers to drive the multi-phase workflow.

## Change Map
- Core workflow or persistence: `core/`.
- UI panels or orchestration: `gui/`.
- LLM adapters or prompts: `llm/`.
- Parsing helpers: `utils/`.
- Phase execution logic: `workers/`.
