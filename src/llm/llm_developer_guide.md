# llm Developer Guide

## Purpose
Defines the LLM provider abstraction, prompt templates, and provider registry used by workers to call CLI-based LLMs.

## Contents
- `base_provider.py`: `BaseLLMProvider` interface, output-format instructions, and `LLMProviderRegistry`.
- `claude_provider.py`: Claude CLI implementation (`claude -p`, one-time permissions setup).
- `gemini_provider.py`: Gemini CLI implementation using stdin and `--yolo`.
- `codex_provider.py`: Codex CLI implementation using `codex exec --full-auto`.
- `prompt_templates.py`: Prompt strings for all workflow phases and review types, plus review display labels.
- `__init__.py`: Registers built-in providers.

## Key Interactions
- Workers fetch providers via `LLMProviderRegistry.get()` and call `build_command()`.
- `BaseLLMProvider.format_prompt()` appends output instructions for JSON, tasks, review, or silent modes.
- Prompt templates are used by `PlanningWorker`, `QuestionWorker`, `ExecutionWorker`, `ReviewWorker`, and `GitWorker`.

## When to Edit LLM
- Add a new provider or model list: create a provider in this folder and register it in `__init__.py`.
- Change output enforcement rules (JSON/tasks/review formatting): `base_provider.py`.
- Add or reorder review types (including UI/UX): `prompt_templates.py`.
- Update question/planning/execution prompts: `prompt_templates.py`.

## Change Map
- Provider behavior or CLI flags: `*_provider.py`.
- Prompt content and review sequencing: `prompt_templates.py`.
- Registry and shared format rules: `base_provider.py`.
