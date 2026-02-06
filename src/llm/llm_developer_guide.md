# llm Developer Guide

## Purpose
Defines the LLM provider abstraction, prompt templates, and provider registry used by workers to call CLI-based LLMs.

## Contents
- `base_provider.py`: `BaseLLMProvider` interface, output-format instructions, and `LLMProviderRegistry`.
- `claude_provider.py`: Claude CLI implementation (`claude -p` with prompt via stdin to avoid Windows newline argument issues), one-time permissions setup, and curated Claude model IDs (including `claude-opus-4-6`).
- `gemini_provider.py`: Gemini CLI implementation using stdin and `--yolo`.
- `codex_provider.py`: Codex CLI implementation using `codex exec --skip-git-repo-check --full-auto`, writing the last message to a file for parsing, and curated Codex model IDs (including `gpt-5.3-codex`).
- `prompt_templates.py`: Prompt strings for all workflow phases and review types (including `general` and `unit_test`), plus review display labels and workspace governance rules (one `.md` per folder excluding system/tooling dirs, read guide before editing, update ancestor guides, <=10 files per folder, <=1000 lines per code file). Question prompts use only the description text and instruct the LLM to edit an existing empty `questions.json` in a single attempt (no fallback prompt). Includes a Q&A-to-definition rewrite prompt that writes `product-description.md` before generating additional question batches.
- `codex_provider.py`: Codex CLI implementation using `codex exec --skip-git-repo-check --full-auto`, writing the last message to a file for parsing.
- `prompt_templates.py`: Prompt strings for all workflow phases and review types, plus review display labels and workspace governance rules (one developer guide `.md` per folder with a root exception, read guide before editing, update ancestor guides, <=10 code files per folder with `.md` excluded, <=1000 lines per code file). Question prompts use only the description text and instruct the LLM to edit an existing empty `questions.json` in a single attempt (no fallback prompt). Task planning prompts instruct the LLM to write directly to `tasks.md` using the project description. Includes a Q&A-to-definition rewrite prompt that writes `product-description.md` before generating additional question batches, formatted via `PromptTemplates.format_definition_rewrite_prompt`.
- `__init__.py`: Registers built-in providers.

## Key Interactions
- Workers fetch providers via `LLMProviderRegistry.get()` and call `build_command()`.
- `BaseLLMProvider.format_prompt()` appends output instructions for JSON, tasks, review, or silent modes.
- Prompt templates are used by `PlanningWorker`, `QuestionWorker`, `ExecutionWorker`, `ReviewWorker`, and `GitWorker`.
 - Providers can optionally supply an output file path for last-message capture (used by Codex).

## When to Edit LLM
- Add a new provider or model list: create a provider in this folder and register it in `__init__.py`.
- Change output enforcement rules (JSON/tasks/review formatting): `base_provider.py`.
- Add or reorder review types (including General, Unit Test, and UI/UX): `prompt_templates.py`.
- Update question/planning/execution prompts or workspace rule messaging (including the Q&A-to-definition rewrite prompt and the tasks.md write instructions): `prompt_templates.py` (includes the five workspace rules).

## Change Map
- Provider behavior or CLI flags: `*_provider.py`.
- Prompt content, workspace compliance sections (the five workspace rules), and review sequencing: `prompt_templates.py`.
- Registry and shared format rules: `base_provider.py`.
