# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AgentHarness is a PySide6 GUI application that orchestrates multi-stage LLM-driven software development workflows. It automates code generation through a 5-phase pipeline with user oversight and approval gates.

## Running the Application

```bash
# Setup virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

**LLM CLI Setup (required):**
- Claude: Run `claude --dangerously-skip-permissions` once before use
- Gemini: Uses `gemini "<prompt>" --yolo`
- Codex: Uses `codex exec --full-auto "<prompt>"`

## Architecture

### 5-Phase Workflow Pipeline

1. **Question Generation** - LLM generates clarifying questions from user's project description (JSON output)
2. **Task Planning** - LLM converts description + answers into `tasks.md` checklist
3. **Main Execution Loop** - Iterative task implementation with `recent-changes.md` tracking
4. **Debug/Review Loop** - 6-pass code review cycle (Architecture, Efficiency, Error Handling, Safety, Testing, Documentation)
5. **Git Operations** - Automatic commit with optional user-approved push

### Key Directories

- `src/core/` - State machine, file manager, session persistence
- `src/gui/` - PySide6 main window, dialogs, and widgets
- `src/llm/` - LLM provider abstraction layer and prompt templates
- `src/workers/` - QRunnable workers for async LLM operations
- `src/utils/` - Markdown and JSON parsing utilities

### Core Patterns

**State Machine** (`src/core/state_machine.py`): Manages phase transitions via `Phase` and `SubPhase` enums. Use `state_machine.transition_to()` for validated transitions.

**Provider Registry** (`src/llm/base_provider.py`): Pluggable LLM backends. Each provider implements `build_command()`, `get_output_instruction()`, and `validate_installation()`.

**Worker Pattern** (`src/workers/base_worker.py`): All async operations use `BaseWorker` subclasses that emit Qt signals for logging, status, and results.

**File Tracking**: Three markdown files drive the workflow:
- `tasks.md` - Task checklist (`- [ ]` unchecked, `- [x]` done)
- `recent-changes.md` - Log of code changes
- `review.md` - Temporary review findings buffer

**Atomic File Operations**: All writes in `FileManager` use temp file + rename pattern.

### Signal Flow

Workers emit signals defined in `src/workers/signals.py`. Main window connects to these for UI updates:
```python
worker.signals.questions_ready.connect(self.on_questions_ready)
worker.signals.log_message.connect(self.log_viewer.append)
```

## LLM Output Format Enforcement

Prompts in `src/llm/prompt_templates.py` enforce strict output formats:
- Question generation: JSON with `{"questions": [...]}` schema
- Task planning: Markdown checklist
- Reviews: Markdown in code blocks

The LLM is constrained to modify only ONE unchecked task per iteration.
