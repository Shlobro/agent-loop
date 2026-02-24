# Core Directory Developer Guide

## Purpose
This directory contains the foundational logic for the AgentHarness application. It manages the application's state, workflow phases, file I/O, project configuration, error handling, and session persistence. It serves as the backend brain that drives the UI and worker processes.

## File Descriptions

### `state_machine.py`
- **Purpose**: Defines the lifecycle of the application. It manages the transition between different execution phases (e.g., `QUESTION_GENERATION`, `TASK_PLANNING`, `MAIN_EXECUTION`).
- **Key Components**:
  - `Phase` & `SubPhase` Enums: Define all possible states of the workflow.
  - `StateContext`: A dataclass that holds the runtime data (e.g., current task, iteration count, LLM configuration, debug flags) passed between states. Default `llm_config` follows the codex/claude baseline profile used by the UI defaults.
  - `StateMachine`: The central class that enforces transition rules (`TRANSITIONS`), emits signals (`phase_changed`, `context_updated`) to the UI, and manages the `StateContext`. During `Phase.AWAITING_ANSWERS`, `get_phase_display_name()` returns `Ready to Continue` when `questions_answered` is already true so the UI reflects post-answer readiness instead of still waiting for input.

### `file_manager.py`
- **Purpose**: Handles all file system operations. It ensures atomic reads and writes to critical project files and maintains the directory structure.
- **Key Features**:
  - Manages artifact files: `tasks.md`, `product-description.md`, `recent-changes.md`, `research.md`, and review files.
  - Ensures existence of governance files (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`) and the `.agentharness` directory. The governance file template includes two headless-mode rules at the top: agents are told the user cannot see their terminal output and must write a phase summary to `answer.md` after completing all their work.
  - `get_stale_governance_files()` returns a list of governance filenames that exist in the project folder but whose content differs from the current recommended template. Used to prompt users to update old files.
  - `append_governance_content(filenames)` appends the recommended template to the end of each named file.
  - `replace_governance_content(filenames)` overwrites each named file with the recommended template.
  - Provides methods for atomic writes (`_atomic_write`) to prevent data corruption.
  - Handles reading/clearing specific files like `answer.md` and error logs.
  - `cap_recent_changes(max_lines=500)` trims `recent-changes.md` to at most 500 lines (keeping the header), dropping the oldest entries. Called after each git operation instead of clearing the file.

### `project_settings.py`
- **Purpose**: Manages persistent configuration for the project.
- **Key Components**:
  - `ProjectSettings`: A dataclass defining all saveable settings (LLM models, debug toggles, UI visibility prefs).
  - `ProjectSettingsManager`: Handles loading/saving settings to `.agentharness/project-settings.json`. It includes normalization logic to handle backward compatibility and default values.

### `session_manager.py`
- **Purpose**: Enables the pause/resume functionality by persisting the application state.
- **Key Features**:
  - `save_session()`: Serializes the `StateMachine`'s current state (phase, context) to `session_state.json`.
  - `load_session()`: Restores the state from the JSON file, allowing the workflow to continue exactly where it left off.

### `debug_settings.py`
- **Purpose**: Centralizes debug configuration constants.
- **Key Features**:
  - `DEBUG_STAGE_LABELS`: Maps internal stage names to human-readable labels.
  - `default_debug_breakpoints()`: Defines default breakpoint behaviors (e.g., pause before/after a stage).

### `error_context.py`
- **Purpose**: structures for error handling and recovery.
- **Key Components**:
  - `ErrorInfo`: A dataclass capturing the full context of an error (traceback, logs, phase info) for the recovery UI.
  - `ErrorRecoveryTracker`: Tracks retry attempts per phase/iteration to prevent infinite error loops.

### `file_watcher.py`
- **Purpose**: Monitors specific files for external changes.
- **Key Features**:
  - `DescriptionFileWatcher`: Uses `QFileSystemWatcher` to detect external edits to `product-description.md`, emitting a signal to prompt the UI to reload the file.

### `chat_history_manager.py`
- **Purpose**: Manages per-project chat history persistence in `.agentharness/chat-history.json`.
- **Key Methods**:
  - `load(working_directory)`: Reads the history file and returns a list of `{role, content, timestamp}` dicts. Returns `[]` on missing file or error.
  - `save(working_directory, messages, limit=50)`: Trims to last `limit` entries and writes atomically via a `.tmp` file.
  - `append_message(working_directory, role, content, limit=50)`: Loads current history, appends one entry, then saves. No-op when `limit == 0`.
  - `clear(working_directory)`: Resets the file to an empty list.
  - `format_for_prompt(messages)`: Returns a formatted block with `=== Recent Conversation History ===` header/footer for injection into LLM prompts.

### `exceptions.py`
- **Purpose**: Defines custom exception classes (e.g., `LLMError`, `FileOperationError`, `StateTransitionError`) used throughout the application for precise error handling.

### `update_markdown_files_with_llm.bat`
- **Purpose**: A utility script for developers. It iterates through all `.md` files in the project and uses a selected CLI LLM (Claude, Codex, Gemini) to update them based on a prompt.

## Key Interactions
- **UI & State**: The `MainWindow` (in `src/ui`) connects to `StateMachine` signals to update the display. It calls `StateMachine.transition_to()` to drive the workflow.
- **Workers & Files**: Worker threads (in `src/workers`) use `FileManager` to read/write task artifacts. They do not access the file system directly to ensure consistency.
- **Configuration**: `ProjectSettings` initializes the `StateContext` with user preferences (like selected LLMs) at the start of a run.
- **Persistence**: `SessionManager` is used by the main application to save state on exit or pause, and restore it on startup.

## How to Modify
- **Adding a Workflow Step**:
  1. Add a new `Phase` or `SubPhase` in `state_machine.py`.
  2. Update `TRANSITIONS` in `StateMachine`.
  3. Implement the corresponding worker logic (outside this folder).
- **Adding a Setting**:
  1. Add the field to `ProjectSettings` dataclass in `project_settings.py`.
  2. Update `_normalize_settings_dict` to provide a default.
  3. Update `StateContext` in `state_machine.py` if the setting needs to be available during execution.
- **Changing File Handling**:
  1. Modify `FileManager` in `file_manager.py`. Always use `_atomic_write` for safety.
