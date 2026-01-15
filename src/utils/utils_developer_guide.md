# utils Developer Guide

## Purpose
Utility parsers for normalizing LLM output and manipulating markdown task lists.

## Contents
- `json_parser.py`: Extracts and normalizes JSON from LLM output (handles fences, noise, and arrays). Validates question schemas.
- `markdown_parser.py`: Parses `- [ ]` checklists into `Task` objects and provides helpers for task mutation and summaries.
- `__init__.py`: Module marker.

## Key Interactions
- Question generation uses `json_parser.parse_questions_json` for strict validation.
- Task planning and execution use `markdown_parser` helpers to count, add, and mark tasks.

## When to Edit Utils
- Add new JSON cleanup rules or support alternative LLM output formats: `json_parser.py`.
- Change task-list rules (nested tasks, caps, auto-ordering): `markdown_parser.py`.
- Add helpers for UI-driven task insertion: `markdown_parser.py` plus `core/file_manager.py`.

## Change Map
- JSON extraction and schema changes: `json_parser.py`.
- Task checklist parsing/mutation: `markdown_parser.py`.
