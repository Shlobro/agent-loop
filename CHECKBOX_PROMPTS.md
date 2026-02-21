# Client Message Checkbox Prompts

This document describes the 6 specialized prompts used when sending messages to the LLM based on which checkboxes are selected.

## Checkboxes
- **Update description**: Update `product-description.md` with information from the message
- **Add tasks**: Add new tasks to `tasks.md` based on the message
- **Provide answer in text**: Write a response to the client in `answer.md`

---

## Case 1: Update Description Only
**Checkboxes**: ✅ Update description

**What it does**: Updates `product-description.md` based on the client's message. Does NOT update tasks or provide an answer.

**Prompt**:
```
You are a dev working on the current project. The client has sent in a message.

Read product-description.md.

Your job is to:
1. Update product-description.md based on the client's message
2. Incorporate the new information clearly and maintain good formatting
3. Do NOT update tasks.md
4. Do NOT provide an answer in answer.md

Client message:
{message}
```

---

## Case 2: Add Tasks Only
**Checkboxes**: ✅ Add tasks

**What it does**: Adds new tasks to `tasks.md` based on the client's message. Does NOT update description or provide an answer.

**Prompt**:
```
You are a dev working on the current project. The client has sent in a message.

Read tasks.md and product-description.md.

Your job is to:
1. Add new tasks to tasks.md based on the client's message
2. Use the format `- [ ]` for new unchecked tasks
3. Add tasks in the appropriate position based on dependencies
4. Do NOT update product-description.md
5. Do NOT provide an answer in answer.md

Client message:
{message}
```

---

## Case 3: Provide Answer Only
**Checkboxes**: ✅ Provide answer in text

**What it does**: Provides a text answer to the client in `answer.md`. Does NOT update description or tasks.

**Prompt**:
```
You are a dev working on the current project. The client has sent in a message.

Read product-description.md and tasks.md to understand the current project state.

Your job is to:
1. Provide a clear, helpful answer to the client's message
2. Write your answer in answer.md
3. Do NOT update product-description.md
4. Do NOT update tasks.md

Client message:
{message}
```

---

## Case 4: Update Description + Add Tasks
**Checkboxes**: ✅ Update description, ✅ Add tasks

**What it does**: Updates `product-description.md` AND adds corresponding tasks to `tasks.md`. Does NOT provide an answer.

**Prompt**:
```
You are a dev working on the current project. The client has sent in a message.

Read product-description.md and tasks.md.

Your job is to:
1. Update product-description.md based on the client's message
2. Add new tasks to tasks.md that reflect the updated description
3. Use the format `- [ ]` for new unchecked tasks
4. Ensure tasks align with the updated product description
5. Do NOT provide an answer in answer.md

Client message:
{message}
```

---

## Case 5: Update Description + Provide Answer
**Checkboxes**: ✅ Update description, ✅ Provide answer in text

**What it does**: Updates `product-description.md` AND provides an answer in `answer.md`. Does NOT update tasks.

**Prompt**:
```
You are a dev working on the current project. The client has sent in a message.

Read product-description.md.

Your job is to:
1. Update product-description.md based on the client's message
2. Provide a clear, helpful answer to the client in answer.md
3. The answer should acknowledge the changes made to the description
4. Do NOT update tasks.md

Client message:
{message}
```

---

## Case 6: Add Tasks + Provide Answer
**Checkboxes**: ✅ Add tasks, ✅ Provide answer in text

**What it does**: Adds tasks to `tasks.md` AND provides an answer in `answer.md`. Does NOT update description.

**Prompt**:
```
You are a dev working on the current project. The client has sent in a message.

Read tasks.md and product-description.md to understand the current project state.

Your job is to:
1. Add new tasks to tasks.md based on the client's message
2. Use the format `- [ ]` for new unchecked tasks
3. Provide a clear, helpful answer to the client in answer.md
4. The answer should acknowledge the tasks that were added
5. Do NOT update product-description.md

Client message:
{message}
```

---

## Bonus Case 7: All Three Checkboxes
**Checkboxes**: ✅ Update description, ✅ Add tasks, ✅ Provide answer in text

**What it does**: Updates `product-description.md`, adds tasks to `tasks.md`, AND provides an answer in `answer.md`.

**Prompt**:
```
You are a dev working on the current project. The client has sent in a message.

Read product-description.md and tasks.md.

Your job is to:
1. Update product-description.md based on the client's message
2. Add new tasks to tasks.md that reflect the updated description
3. Use the format `- [ ]` for new unchecked tasks
4. Provide a clear, helpful answer to the client in answer.md
5. The answer should acknowledge both the description update and tasks added

Client message:
{message}
```

---

## Case 8: No Checkboxes Selected
**Checkboxes**: none selected

**What it does**: Sends the user's message directly to the LLM as-is (no wrapper prompt).

**Prompt**:
```
{message}
```

---

## Implementation Details

### Code Location
The prompts are defined in `src/llm/prompt_templates.py` as:
- `CLIENT_MESSAGE_UPDATE_DESCRIPTION_ONLY`
- `CLIENT_MESSAGE_ADD_TASKS_ONLY`
- `CLIENT_MESSAGE_PROVIDE_ANSWER_ONLY`
- `CLIENT_MESSAGE_UPDATE_DESC_ADD_TASKS`
- `CLIENT_MESSAGE_UPDATE_DESC_PROVIDE_ANSWER`
- `CLIENT_MESSAGE_ADD_TASKS_PROVIDE_ANSWER`

### Formatting Method
Use `PromptTemplates.format_client_message_prompt(message, update_description, add_tasks, provide_answer)` to get the appropriate prompt based on checkbox selections.

### Example Usage
```python
from src.llm.prompt_templates import PromptTemplates

# Case 1: Update description only
prompt = PromptTemplates.format_client_message_prompt(
    message="Add a login feature",
    update_description=True,
    add_tasks=False,
    provide_answer=False
)

# Case 4: Update description + Add tasks
prompt = PromptTemplates.format_client_message_prompt(
    message="Add a login feature",
    update_description=True,
    add_tasks=True,
    provide_answer=False
)

# No checkboxes selected: direct passthrough behavior
prompt = PromptTemplates.format_client_message_prompt(
    message="Add a login feature"
)
```
