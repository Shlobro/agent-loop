# llm Developer Guide

## Purpose
Defines the LLM provider abstraction, prompt templates, and provider registry used by workers to call CLI-based LLMs.

## Contents
- `base_provider.py`: `BaseLLMProvider` interface, output-format instructions, and `LLMProviderRegistry`.
- `claude_provider.py`: Claude CLI implementation (`claude -p` with prompt via stdin), one-time permissions setup, and curated Claude model IDs.
- `gemini_provider.py`: Gemini CLI implementation using stdin and `--yolo`.
- `codex_provider.py`: Codex CLI implementation using `codex exec --skip-git-repo-check --full-auto`, writing the last message to a file for parsing.
- `prompt_templates.py`: Prompt strings for all workflow phases and review types (General, Architecture, Efficiency, Error Handling, Unit Test, UI/UX), plus review display labels and per-type review file naming (`review/<type>.md`). Includes a git prompt that generates only a commit message file (no LLM push prompt) and now embeds a git status/diff snapshot directly in the prompt so the LLM does not need to run `git diff`. Review prompts are issue-only (no positive notes) and require leaving the target file empty when no issues are found.
- `__init__.py`: Registers built-in providers.

## Key Interactions
- Workers fetch providers via `LLMProviderRegistry.get()` and call `build_command()`.
- `BaseLLMProvider.format_prompt()` appends output instructions for JSON, tasks, review, or silent modes.
- Prompt templates are used by `PlanningWorker`, `QuestionWorker`, `ExecutionWorker`, `ReviewWorker`, and `GitWorker`.
 - Providers can optionally supply an output file path for last-message capture (used by Codex).

## When to Edit LLM
- Add a new provider or model list: create a provider in this folder and register it in `__init__.py`.
- Change output enforcement rules (JSON/tasks/review formatting): `base_provider.py`.
- Add or reorder review types (including General, Unit Test, and UI/UX) or change per-type review file naming: `prompt_templates.py`.
- Update question/planning/execution prompts (including the Q&A-to-definition rewrite prompt and the tasks.md write instructions): `prompt_templates.py`.

## Change Map
- Provider behavior or CLI flags: `*_provider.py`.
- Prompt content and review sequencing: `prompt_templates.py`.
- Registry and shared format rules: `base_provider.py`.
