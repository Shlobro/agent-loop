# llm Developer Guide

## Purpose
Defines the LLM provider abstraction, prompt templates, and provider registry used by workers to call CLI-based LLMs.

## Contents
- `base_provider.py`: `BaseLLMProvider` interface, output-format instructions, and `LLMProviderRegistry`.
- `claude_provider.py`: Claude CLI implementation (`claude -p` with prompt via stdin), one-time permissions setup, and curated Claude model IDs.
- `gemini_provider.py`: Gemini CLI implementation using stdin and `--yolo`.
- `codex_provider.py`: Codex CLI implementation using `codex exec --skip-git-repo-check --full-auto`, sending prompts via stdin (`-`) to avoid Windows argument-escaping/newline issues, and writing the last message to a file for parsing. For portability, when a working directory is provided it also passes `--cd <working_directory>` and `--add-dir <working_directory>` so Codex sandbox write scope follows the selected project. Supports reasoning effort levels (low, medium, high, xhigh) via model ID suffixes (e.g., `:high`).
- `prompt_templates.py`: Prompt strings for all workflow phases and review types (General, Functionality, Architecture, Efficiency, Error Handling, Safety, Testing, Documentation, UI/UX), plus review display labels and per-type review file naming (`review/<type>.md`). Includes a dedicated post-planning research prompt that fills `research.md` using `product-description.md` and `tasks.md`. The planning prompt focuses on writing `tasks.md` from `product-description.md`. The main execution prompt dynamically adjusts between single-task and multi-task wording based on the `tasks_per_iteration` setting and explicitly tells the coder stage to read `research.md` when available. Includes an optional pre-review unit-test-update prompt that runs before review cycles and uses `git diff` to decide whether tests should be added or edited. Includes a git prompt that generates only a commit message file (no LLM push prompt) and embeds a git status/diff snapshot directly in the prompt so the LLM does not need to run `git diff`. Includes client message prompts with checkbox-based control (6 combinations) and direct passthrough behavior when no checkboxes are selected (the user message is sent as-is). Review prompts are issue-only (no positive notes) and require leaving the target file empty when no issues are found. Also includes an onboarding prompt that creates `product-description.md` from an existing non-empty repository without modifying governance files.
- `__init__.py`: Registers built-in providers.

## Key Interactions
- Workers fetch providers via `LLMProviderRegistry.get()` and call `build_command()`.
- `BaseLLMProvider.format_prompt()` appends output instructions for JSON, tasks, review, or silent modes.
- Prompt templates are used by `PlanningWorker`, `QuestionWorker`, `ExecutionWorker`, `ReviewWorker`, and `GitWorker`.
 - Providers can optionally supply an output file path for last-message capture (used by Codex).

## When to Edit LLM
- Add a new provider or model list: create a provider in this folder and register it in `__init__.py`.
- Change output enforcement rules (JSON/tasks/review formatting): `base_provider.py`.
- Add or reorder review types (including General and UI/UX), tune the optional pre-review unit-test-update prompt, or change per-type review file naming: `prompt_templates.py`.
- Update question/research/planning/execution prompts (including the Q&A-to-definition rewrite prompt, the repository-to-description bootstrap prompt, and the tasks.md write instructions): `prompt_templates.py`.

## Change Map
- Provider behavior or CLI flags: `*_provider.py`.
- Prompt content and review sequencing: `prompt_templates.py`.
- Registry and shared format rules: `base_provider.py`.
