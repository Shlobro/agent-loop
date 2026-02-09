# Checkbox Message Flow Diagram

## Signal Flow

```
User Interface (chat_panel.py)
    │
    │ User clicks "Send Message"
    │
    ├─ Read checkbox states:
    │   • update_description: bool
    │   • add_tasks: bool
    │   • provide_answer: bool
    │
    └─ Emit signal: message_sent(message, update_desc, add_tasks, provide_answer)
              │
              │ Qt Signal Connection
              ▼
MainWindow.on_client_message_sent()
    │
    ├─ Store message + checkbox states in queue
    │   {
    │     "id": uuid,
    │     "content": message,
    │     "update_description": bool,
    │     "add_tasks": bool,
    │     "provide_answer": bool,
    │     "status": "queued"
    │   }
    │
    └─ If not in workflow → Process immediately
              │
              ▼
workflow_runner._process_client_messages()
    │
    ├─ Extract checkbox states from queue
    │
    └─ Create ClientMessageWorker with checkbox params
              │
              ▼
ClientMessageWorker.execute()
    │
    ├─ Pass checkbox states to prompt formatter
    │   PromptTemplates.format_client_message_prompt(
    │       message,
    │       update_description,
    │       add_tasks,
    │       provide_answer
    │   )
    │
    ├─ Prompt formatter selects appropriate prompt:
    │
    │   No checkboxes → Legacy auto-detect
    │
    │   1 checkbox:
    │   • update_description → UPDATE_DESCRIPTION_ONLY
    │   • add_tasks → ADD_TASKS_ONLY
    │   • provide_answer → PROVIDE_ANSWER_ONLY
    │
    │   2 checkboxes:
    │   • update_desc + add_tasks → UPDATE_DESC_ADD_TASKS
    │   • update_desc + provide_answer → UPDATE_DESC_PROVIDE_ANSWER
    │   • add_tasks + provide_answer → ADD_TASKS_PROVIDE_ANSWER
    │
    │   3 checkboxes → All three behaviors combined
    │
    └─ Call LLM with selected prompt
              │
              ▼
LLM Processing
    │
    ├─ Updates files based on prompt instructions:
    │   • product-description.md (if instructed)
    │   • tasks.md (if instructed)
    │   • answer.md (if instructed)
    │
    └─ Return result
              │
              ▼
workflow_runner.on_client_message_complete()
    │
    ├─ Detect what changed by comparing files
    ├─ Update UI with changes
    ├─ Show answer dialog if answer.md has content
    └─ Show status message in chat panel
```

## Prompt Selection Matrix

| Update Desc | Add Tasks | Provide Answer | Prompt Used |
|------------|-----------|----------------|-------------|
| ❌ | ❌ | ❌ | Auto-detect (legacy) |
| ✅ | ❌ | ❌ | UPDATE_DESCRIPTION_ONLY |
| ❌ | ✅ | ❌ | ADD_TASKS_ONLY |
| ❌ | ❌ | ✅ | PROVIDE_ANSWER_ONLY |
| ✅ | ✅ | ❌ | UPDATE_DESC_ADD_TASKS |
| ✅ | ❌ | ✅ | UPDATE_DESC_PROVIDE_ANSWER |
| ❌ | ✅ | ✅ | ADD_TASKS_PROVIDE_ANSWER |
| ✅ | ✅ | ✅ | All three (combined) |

## File Update Logic

### When Update Description is checked:
```python
# LLM reads product-description.md
# LLM rewrites product-description.md with new info
# workflow_runner detects change via file comparison
# UI updates description panel
```

### When Add Tasks is checked:
```python
# LLM reads tasks.md and product-description.md
# LLM appends new tasks in format: - [ ] Task name
# workflow_runner detects change via file comparison
# UI updates task counts
```

### When Provide Answer is checked:
```python
# LLM reads context (description/tasks)
# LLM writes answer to answer.md
# workflow_runner reads answer.md
# Shows modal dialog with answer
# Shows answer inline in chat history
```

## UI Component Tree

```
ChatPanel (chat_panel.py)
│
├─ Message History Display (QTextBrowser)
│   └─ Shows: message, status, timestamp, LLM answers
│
├─ Input Area (QTextEdit)
│   └─ Placeholder changes based on description state
│
├─ Checkbox Controls (QHBoxLayout)
│   ├─ update_description_cb (QCheckBox)
│   ├─ add_tasks_cb (QCheckBox)
│   └─ provide_answer_cb (QCheckBox)
│
└─ Send Button (QPushButton)
    └─ Reads checkboxes and emits signal
```

## State Management

### Message Queue Structure:
```python
ctx.pending_client_messages = [
    {
        "id": "uuid-1",
        "content": "Add login feature",
        "timestamp": "2024-01-01T12:00:00",
        "status": "queued",  # or "processing" or "completed"
        "update_description": True,
        "add_tasks": True,
        "provide_answer": False
    },
    # ... more messages
]
```

### Processing States:
1. **queued** - Message added to queue, waiting to be processed
2. **processing** - Worker is actively processing the message
3. **completed** - Message processed, results displayed

## Error Handling

The system handles various scenarios:

1. **Empty message** - Send button does nothing
2. **No checkboxes + no description** - Initializes description
3. **No checkboxes + has description** - Auto-detect mode (legacy behavior)
4. **Checkboxes selected** - Uses appropriate specialized prompt
5. **Message during workflow** - Queues and processes at iteration boundary
6. **Message when idle** - Processes immediately

## Backward Compatibility

The implementation maintains full backward compatibility:

```python
# Old code (still works):
message_sent.emit(message)
# → Received as: on_client_message_sent(message, False, False, False)
# → All checkbox params default to False
# → format_client_message_prompt receives (message, None, None, None)
# → Uses legacy auto-detect prompt

# New code:
message_sent.emit(message, True, False, True)
# → Received as: on_client_message_sent(message, True, False, True)
# → format_client_message_prompt receives (message, True, False, True)
# → Uses UPDATE_DESC_PROVIDE_ANSWER prompt
```
