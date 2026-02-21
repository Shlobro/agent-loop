"""Prompt templates for all LLM interactions."""

from enum import Enum
from typing import Union


class ReviewType(Enum):
    """Types of code review."""
    GENERAL = "general"
    FUNCTIONALITY = "functionality"
    ARCHITECTURE = "architecture"
    EFFICIENCY = "efficiency"
    ERROR_HANDLING = "error_handling"
    SAFETY = "safety"
    TESTING = "testing"
    UNIT_TEST = "unit_test"
    DOCUMENTATION = "documentation"
    UI_UX = "ui_ux"


class PromptTemplates:
    """Central repository for all LLM prompt templates."""

    # =========================================================================
    # Phase 1: Question Generation (Batch mode)
    # =========================================================================
    QUESTION_GENERATION_PROMPT = (
        """
read the product-description.md file this is currently what we know the client wants.
we want to send the client some questions to clarify a few things i want you come up with {question_count} questions to clarify.
provide the user with 3-5 possible answers for each question.
the format of the json should be: {{"questions":[{{"question":"...","options":["...","..."]}}]}}.\n\n
there already exists an empty questions.json file. edit it and put the questions there.
Do not implement any code I only want the clarifying questions in the `questions.json` file.
Do not create any new files, only edit the existing questions.json with new questions and answers.
        """
    )
    # QUESTION_GENERATION_PROMPT = (
    #     'your job is to edit `questions.json` file with {question_count} questions to clarify '
    #     'exactly what the user wants to make. provide the user with 3-5 possible '
    #     'answers for each question. the format of the json should be '
    #     '{{"questions":[{{"question":"...","options":["...","..."]}}]}}.\n\n'
    #     'there already exists an empty questions.json file. edit it and put the questions there. '
    #     'Write the JSON to `questions.json` in the working directory: {working_directory}. '
    #     'Do not implement any code I only want the clarifying questions in the `questions.json` file. '
    #     'Do not create any new files, only edit the existing questions.json with new questions and answers. '
    #     'in the project description the user inputted was: "{description}".'
    # )

    # =========================================================================
    # Question Follow-up: Q&A -> Product Definition Rewrite
    # =========================================================================
    DEFINITION_REWRITE_PROMPT = '''
update product-description.md.
Rewrite the project description into a clear product definition using the original description and the clarifying Q&A.
to be clear the client has sent us a product description and we have sent him clarifying questions, the client has responded to those questions and now we need to create a new updated product description based on these questions and the original product description

ORIGINAL DESCRIPTION:
{description}

CLARIFYING QUESTIONS AND ANSWERS:
{answers}
'''

    # =========================================================================
    # Phase 2: Task Planning
    # =========================================================================
    RESEARCH_PROMPT = '''
I want you to search online and fill in the research.md file.
We already have product-description.md and tasks.md.
Use both files while conducting research.
Fill in research.md with any information a developer should have while working on this product and planned tasks.

Requirements for research.md:
- Keep it practical and implementation-focused for engineers.
- Include relevant standards, APIs, libraries, constraints, edge cases, and security/privacy considerations.
- Include assumptions and open questions that should be validated with the client.
- Do not write tasks in this file.
- Do not modify any files other than research.md.
'''

    TASK_PLANNING = '''
I want you to make a task list in the tasks.md file.
Do not implement any code; only write the task list.
The tasks should be created according to the gap of what currently exists and what is in product-description.md.

OUTPUT FORMAT (write directly into tasks.md):
- Use a markdown checklist with `- [ ]` for each task (unchecked checkbox).
- Order tasks by dependency (prerequisites first).
- Be specific and actionable; each task should be completable in one coding session.
- Include setup, implementation, testing, and documentation tasks.
- Do not use nested tasks or sub-items.
- Each task should be self-contained.
'''

    # =========================================================================
    # Phase 3: Main Execution
    # =========================================================================
    MAIN_EXECUTION_SINGLE = '''
INSTRUCTIONS:
1. Read the recent-changes.md
2. Read research.md if it exists and use it as context
3. Choose exactly ONE incomplete task from tasks.md list (marked with `- [ ]`)
4. Implement that task completely and thoroughly
5. After implementing, update the recent-changes.md file with what you changed
6. Mark the task as complete in tasks.md by changing `- [ ]` to `- [x]`
7. If you discover additional tasks that need to be done, add them to tasks.md but do not execute them

CRITICAL RULES:
- Only work on ONE task and complete it do not complete more than 1 task
- Only mark one task as complete once you have fully completed it
- Be thorough - the task should be fully complete before marking done
- Always update both tasks.md and recent-changes.md
'''

    MAIN_EXECUTION_MULTI = '''
INSTRUCTIONS:
1. Read the recent-changes.md
2. Read research.md if it exists and use it as context
3. Choose up to {tasks_per_iteration} incomplete tasks from tasks.md list (marked with `- [ ]`)
4. Implement each chosen task completely and thoroughly
5. After implementing, update the recent-changes.md file with what you changed
6. Mark each completed task in tasks.md by changing `- [ ]` to `- [x]`
7. If you discover additional tasks that need to be done, add them to tasks.md but do not execute them

CRITICAL RULES:
- Work on up to {tasks_per_iteration} tasks and complete them
- Only mark a task as complete once you have fully completed it
- Be thorough - each task should be fully complete before marking done
- Always update both tasks.md and recent-changes.md
'''


    # =========================================================================
    # Phase 4: Review Prompts
    # =========================================================================
    PRE_REVIEW_UNIT_TEST_UPDATE = '''
inspect recent code changes and decide whether unit tests should be added or updated.

Use `git diff` to inspect changes.

If tests are needed:
- Add new unit tests and/or update existing unit tests to match the code changes.
- Keep tests deterministic and isolated.
- Cover important edge cases and error paths that changed.

If tests are not needed, do not make code changes.

Always update recent-changes.md if you add or edit tests.
'''

    REVIEW_PROMPTS = {
        ReviewType.GENERAL: '''
Review the recent code changes.

Use `git diff` to inspect changes.

Write findings to `{review_file}` using only issues.
If there are no issues, leave `{review_file}` empty.
Do not include positive observations.
''',

        ReviewType.FUNCTIONALITY: '''
Review the recent code changes for FUNCTIONALITY concerns.

Use `git diff` to inspect changes.

Focus only on FUNCTIONALITY bugs, issues, and errors.

Write findings to `{review_file}` using only issues.
If there are no issues, leave `{review_file}` empty.
Do not include positive observations.
''',

        ReviewType.ARCHITECTURE: '''
Review the recent code changes for ARCHITECTURAL concerns.

Use `git diff` to inspect changes.

Focus only on ARCHITECTURAL bugs, issues, and errors.

Write findings to `{review_file}` using only issues.
If there are no issues, leave `{review_file}` empty.
Do not include positive observations.
''',

        ReviewType.EFFICIENCY: '''
Review the recent code changes for EFFICIENCY concerns.

Use `git diff` to inspect changes.

Focus only on EFFICIENCY bugs, issues, and errors.

Write findings to `{review_file}` using only issues.
If there are no issues, leave `{review_file}` empty.
Do not include positive observations.
''',

        ReviewType.ERROR_HANDLING: '''
Review the recent code changes for ERROR HANDLING concerns.

Use `git diff` to inspect changes.

Focus only on ERROR HANDLING bugs, issues, and errors.

Write findings to `{review_file}` using only issues.
If there are no issues, leave `{review_file}` empty.
Do not include positive observations.
''',

        ReviewType.SAFETY: '''
Review the recent code changes for SAFETY and SECURITY concerns.

Use `git diff` to inspect changes.

Focus only on SAFETY and SECURITY bugs, issues, and errors.

Write findings to `{review_file}` using only issues.
If there are no issues, leave `{review_file}` empty.
Do not include positive observations.
''',

        ReviewType.TESTING: '''
Review the recent code changes for TESTING concerns.

Use `git diff` to inspect changes.

Focus only on TESTING bugs, issues, and errors.

Write findings to `{review_file}` using only issues.
If there are no issues, leave `{review_file}` empty.
Do not include positive observations.
''',

        ReviewType.UNIT_TEST: '''
Review the recent code changes for UNIT TEST concerns.

Use `git diff` to inspect changes.

Focus only on bugs, issues, and errors:
- Missing unit tests for new or changed logic
- Non-deterministic or non-isolated tests
- Missing edge cases and error-path assertions

Write findings to `{review_file}` using only issues.
If there are no issues, leave `{review_file}` empty.
Do not include positive observations.
''',

        ReviewType.DOCUMENTATION: '''
Review the recent code changes for DOCUMENTATION concerns.

Use `git diff` to inspect changes.

Focus only on DOCUMENTATION bugs, issues, and errors:

Write findings to `{review_file}` using only issues.
If there are no issues, leave `{review_file}` empty.
Do not include positive observations.
''',

        ReviewType.UI_UX: '''
Review the recent code changes for UI/UX concerns.

Use `git diff` to inspect changes.

Focus only on UI/UX bugs, issues, and errors:

Write findings to `{review_file}` using only issues.
If there are no issues, leave `{review_file}` empty.
Do not include positive observations.
''',
    }

    # =========================================================================
    # Phase 4: Fixer Prompt
    # =========================================================================
    FIXER = '''A code review has been performed for {review_type}.


Your task:
1. Read each issue found in the review
2. For each issue, decide: Do you AGREE or DISAGREE?
3. For issues you AGREE with: Implement the fix

After making changes:
1. Update recent-changes.md with what you fixed

REVIEW FINDINGS:
{review_content}
'''

    # =========================================================================
    # Error Recovery: LLM Error Fixing
    # =========================================================================
    ERROR_FIX_PROMPT = '''I was doing {phase} and got an error. Can you fix it?

Please write your analysis and solution to a file called `error-conclusion.md`.

In the error-conclusion.md file, include:
1. What went wrong and why
2. What you did to fix it
3. Whether the fix should resolve the issue

If you made code changes to fix the error, also update recent-changes.md.

The error message:
{error_summary}

FULL ERROR DETAILS:
{full_error}

RECENT LOG CONTEXT:
{recent_logs}

WORKING DIRECTORY: {working_directory}'''

    # =========================================================================
    # Client Message Handler (Legacy - kept for backward compatibility)
    # =========================================================================
    CLIENT_MESSAGE_HANDLER_PROMPT = """You are a dev working on the current project. The client has sent in a message.

I want you to look at product-description.md and at tasks.md.

Your job is to:
1. Determine if the product-description.md needs to be updated based on the client's message
2. If yes, update product-description.md with the new information
3. After updating product description (if you did), check if tasks.md needs updating
4. If tasks.md needs updating, update it accordingly

If the message requires a direct answer (not just updating files):
- Put your response in answer.md

If all that is needed is updating product-description.md and/or tasks.md:
- Leave answer.md empty

Client message:
{message}
"""

    # =========================================================================
    # Client Message Handler - Checkbox-based Prompts
    # =========================================================================

    # Case 1: Update description only
    CLIENT_MESSAGE_UPDATE_DESCRIPTION_ONLY = """You are a dev working on the current project. The client has sent in a message.

Read product-description.md.

Your job is to:
1. Update product-description.md based on the client's message
2. Incorporate the new information clearly and maintain good formatting
3. Do NOT update tasks.md
4. Do NOT provide an answer in answer.md

Client message:
{message}
"""

    # Case 2: Add tasks only
    CLIENT_MESSAGE_ADD_TASKS_ONLY = """You are a dev working on the current project. The client has sent in a message.

Read tasks.md and product-description.md.

Your job is to:
1. Add new tasks to tasks.md based on the client's message
2. Use the format `- [ ]` for new unchecked tasks
3. Add tasks in the appropriate position based on dependencies
4. Do NOT update product-description.md
5. Do NOT provide an answer in answer.md

Client message:
{message}
"""

    # Case 3: Provide answer only
    CLIENT_MESSAGE_PROVIDE_ANSWER_ONLY = """You are a dev working on the current project. The client has sent in a message.

Read product-description.md and tasks.md to understand the current project state.

Your job is to:
1. Provide a clear, helpful answer to the client's message
2. Write your answer in answer.md
3. Do NOT update product-description.md
4. Do NOT update tasks.md

Client message:
{message}
"""

    # Case 4: Update description + Add tasks
    CLIENT_MESSAGE_UPDATE_DESC_ADD_TASKS = """You are a dev working on the current project. The client has sent in a message.

Read product-description.md and tasks.md.

Your job is to:
1. Update product-description.md based on the client's message
2. Add new tasks to tasks.md that reflect the updated description
3. Use the format `- [ ]` for new unchecked tasks
4. Ensure tasks align with the updated product description
5. Do NOT provide an answer in answer.md

Client message:
{message}
"""

    # Case 5: Update description + Provide answer
    CLIENT_MESSAGE_UPDATE_DESC_PROVIDE_ANSWER = """You are a dev working on the current project. The client has sent in a message.

Read product-description.md.

Your job is to:
1. Update product-description.md based on the client's message
2. Provide a clear, helpful answer to the client in answer.md
3. The answer should acknowledge the changes made to the description
4. Do NOT update tasks.md

Client message:
{message}
"""

    # Case 6: Add tasks + Provide answer
    CLIENT_MESSAGE_ADD_TASKS_PROVIDE_ANSWER = """You are a dev working on the current project. The client has sent in a message.

Read tasks.md and product-description.md to understand the current project state.

Your job is to:
1. Add new tasks to tasks.md based on the client's message
2. Use the format `- [ ]` for new unchecked tasks
3. Provide a clear, helpful answer to the client in answer.md
4. The answer should acknowledge the tasks that were added
5. Do NOT update product-description.md

Client message:
{message}
"""

    # =========================================================================
    # Chat-to-Description Initialization
    # =========================================================================
    DESCRIPTION_INITIALIZE_PROMPT = """You are initializing a new product description from the client's first message.

The client has provided their initial project description or request.
Your job is to write a clear, well-formatted product description into product-description.md.

Guidelines:
- Write the description in a clear, structured format
- Include all key details from the client's message
- Format it as a proper product description (not just copying verbatim)
- Be concise but comprehensive
- Use markdown formatting where appropriate

Client message:
{message}

Write the formatted product description directly into product-description.md.
"""

    # =========================================================================
    # Chat-to-Description Update
    # =========================================================================
    DESCRIPTION_UPDATE_PROMPT = """You are updating the product description based on a client message.

Read the current product-description.md file.
The client has sent a message that may require updating the product description.

Your job is to:
1. Analyze the client's message
2. Determine if it requires updating product-description.md
3. If yes, update product-description.md to incorporate the new information
4. If no update is needed, do nothing to product-description.md

Client message:
{message}

If an update is needed, modify product-description.md accordingly.
"""

    # =========================================================================
    # Existing Repo -> Initial Description Bootstrap
    # =========================================================================
    REPOSITORY_DESCRIPTION_BOOTSTRAP_PROMPT = """You are onboarding an existing codebase into AgentHarness.

Goal:
- Create an initial `product-description.md` by analyzing this repository.

Instructions:
1. Inspect the existing repository structure and key source/config/docs files.
2. Infer what product currently exists, who it is for, and what it does today.
3. Write a clear, practical product description into `product-description.md`.
4. Keep the description developer-friendly and implementation-focused.
5. Include a short "Assumptions / Open Questions" section for uncertain parts.

Constraints:
- Do not modify files other than `product-description.md`.
- Do not modify governance files (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`) if they already exist.
- Do not create tasks in this step.
- If the repository is unclear, still produce the best description you can from available evidence.
"""

    # =========================================================================
    # Phase 5: Git Operations
    # =========================================================================
    GIT_COMMIT_MESSAGE = '''Create a git commit message and write it to `{message_file}`.

Rules:
1. Only edit `{message_file}`.
2. Write a concise commit message following standards.
3. Use the provided git status and diff snapshot; do not run git commands.
4. Do not create or modify any other file.

Commit message quality:
- Start with a verb (Add, Fix, Update, Implement, Refactor, etc.)
- Be concise but specific
- Reflect the main change just completed in the provided git diff snapshot and in the recent changes file

GIT STATUS (PORCELAIN):
{git_status}

GIT DIFF:
{git_diff}
'''

    @classmethod
    def get_review_prompt(cls, review_type: ReviewType,
                          review_file: str = "review.md") -> str:
        """Get the review prompt for a specific review type."""
        template = cls.REVIEW_PROMPTS.get(review_type, "")
        if not template:
            return ""
        return template.format(review_file=review_file)

    @classmethod
    def get_all_review_types(cls) -> list:
        """Get list of all review types in order."""
        return [
            ReviewType.GENERAL,
            ReviewType.FUNCTIONALITY,
            ReviewType.ARCHITECTURE,
            ReviewType.EFFICIENCY,
            ReviewType.ERROR_HANDLING,
            ReviewType.SAFETY,
            ReviewType.TESTING,
            ReviewType.DOCUMENTATION,
            ReviewType.UI_UX,
        ]

    @classmethod
    def get_review_display_name(cls, review_type: Union[ReviewType, str]) -> str:
        """Return a user-facing review label."""
        if isinstance(review_type, ReviewType):
            value = review_type.value
        else:
            value = str(review_type)
        if value == ReviewType.UI_UX.value:
            return "UI/UX"
        return value.replace('_', ' ').title()

    @classmethod
    def get_review_filename(cls, review_type: Union[ReviewType, str]) -> str:
        """Return the relative review file path for a review type."""
        if isinstance(review_type, ReviewType):
            value = review_type.value
        else:
            value = str(review_type)
        return f"review/{value}.md"

    @classmethod
    def format_question_prompt(cls, description: str, question_count: int,
                               previous_qa: list, working_directory: str = ".") -> str:
        """Format the question generation prompt (batch mode)."""
        return cls.QUESTION_GENERATION_PROMPT.format(
            description=description,
            question_count=question_count,
            working_directory=working_directory
        )

    @classmethod
    def format_definition_rewrite_prompt(cls, description: str,
                                         qa_pairs: list = None,
                                         working_directory: str = ".") -> str:
        """Format the prompt to rewrite Q&A into a product definition."""
        if qa_pairs:
            qa_lines = []
            for i, qa in enumerate(qa_pairs, 1):
                qa_lines.append(f"Q{i}: {qa['question']}")
                qa_lines.append(f"A{i}: {qa['answer']}")
                qa_lines.append("")
            answers_text = "\n".join(qa_lines).strip()
        else:
            answers_text = "(none)"
        return cls.DEFINITION_REWRITE_PROMPT.format(
            description=description,
            answers=answers_text,
            working_directory=working_directory
        )

    @classmethod
    def format_planning_prompt(cls, description: str, answers: dict,
                               qa_pairs: list = None,
                               working_directory: str = ".") -> str:
        """Format the task planning prompt.

        Args:
            description: The summarized project description
            answers: Dict of {question_id: answer} (legacy format, unused for planning)
            qa_pairs: List of {"question": ..., "answer": ...} (new format, unused for planning)
        """
        return cls.TASK_PLANNING.format(
            description=description,
            working_directory=working_directory
        )

    @classmethod
    def format_research_prompt(cls, working_directory: str = ".") -> str:
        """Format the prompt for the post-planning research phase."""
        return cls.RESEARCH_PROMPT.format(working_directory=working_directory)

    @classmethod
    def format_execution_prompt(cls, working_directory: str,
                                recent_changes: str, tasks: str,
                                tasks_per_iteration: int = 1) -> str:
        """Format the main execution prompt."""
        if tasks_per_iteration <= 1:
            template = cls.MAIN_EXECUTION_SINGLE
        else:
            template = cls.MAIN_EXECUTION_MULTI
        return template.format(
            working_directory=working_directory,
            recent_changes=recent_changes or "(No recent changes yet)",
            tasks=tasks,
            tasks_per_iteration=tasks_per_iteration
        )

    @classmethod
    def format_fixer_prompt(cls, review_type: str,
                            review_content: str) -> str:
        """Format the fixer prompt."""
        return cls.FIXER.format(
            review_type=review_type,
            review_content=review_content
        )

    @classmethod
    def format_pre_review_unit_test_prompt(cls) -> str:
        """Format prompt for the optional pre-review unit test update phase."""
        return cls.PRE_REVIEW_UNIT_TEST_UPDATE

    @classmethod
    def format_git_commit_message_prompt(cls, message_file: str,
                                         git_status: str,
                                         git_diff: str) -> str:
        """Format prompt for commit-message-only generation."""
        return cls.GIT_COMMIT_MESSAGE.format(
            message_file=message_file,
            git_status=git_status,
            git_diff=git_diff
        )

    @classmethod
    def format_error_fix_prompt(cls, phase: str, error_summary: str,
                                full_error: str, recent_logs: str,
                                working_directory: str) -> str:
        """Format prompt for LLM to analyze and fix a workflow error."""
        return cls.ERROR_FIX_PROMPT.format(
            phase=phase,
            error_summary=error_summary,
            full_error=full_error,
            recent_logs=recent_logs,
            working_directory=working_directory
        )

    @staticmethod
    def format_client_message_prompt(message: str, update_description: bool = None,
                                     add_tasks: bool = None, provide_answer: bool = None,
                                     chat_history: list = None) -> str:
        """
        Format the client message handler prompt based on checkbox selections.

        Args:
            message: The client's message
            update_description: If True, update product-description.md
            add_tasks: If True, add tasks to tasks.md
            provide_answer: If True, provide answer in answer.md
            chat_history: Optional list of prior conversation entries

        If no checkboxes are specified (all None), uses legacy auto-detect behavior.
        If all checkboxes are explicitly unchecked (all False), sends message as-is.
        """
        from ..core.chat_history_manager import ChatHistoryManager
        history_block = ""
        if chat_history:
            formatted = ChatHistoryManager.format_for_prompt(chat_history)
            if formatted:
                history_block = formatted + "\n\n"

        # Legacy behavior - auto-detect what to do
        if update_description is None and add_tasks is None and provide_answer is None:
            prompt = PromptTemplates.CLIENT_MESSAGE_HANDLER_PROMPT.format(message=message)
            return history_block + prompt

        # Convert None to False for easier logic
        update_description = update_description or False
        add_tasks = add_tasks or False
        provide_answer = provide_answer or False

        # Case 1: Update description only
        if update_description and not add_tasks and not provide_answer:
            prompt = PromptTemplates.CLIENT_MESSAGE_UPDATE_DESCRIPTION_ONLY.format(message=message)
            return history_block + prompt

        # Case 2: Add tasks only
        if add_tasks and not update_description and not provide_answer:
            prompt = PromptTemplates.CLIENT_MESSAGE_ADD_TASKS_ONLY.format(message=message)
            return history_block + prompt

        # Case 3: Provide answer only
        if provide_answer and not update_description and not add_tasks:
            prompt = PromptTemplates.CLIENT_MESSAGE_PROVIDE_ANSWER_ONLY.format(message=message)
            return history_block + prompt

        # Case 4: Update description + Add tasks
        if update_description and add_tasks and not provide_answer:
            prompt = PromptTemplates.CLIENT_MESSAGE_UPDATE_DESC_ADD_TASKS.format(message=message)
            return history_block + prompt

        # Case 5: Update description + Provide answer
        if update_description and provide_answer and not add_tasks:
            prompt = PromptTemplates.CLIENT_MESSAGE_UPDATE_DESC_PROVIDE_ANSWER.format(message=message)
            return history_block + prompt

        # Case 6: Add tasks + Provide answer
        if add_tasks and provide_answer and not update_description:
            prompt = PromptTemplates.CLIENT_MESSAGE_ADD_TASKS_PROVIDE_ANSWER.format(message=message)
            return history_block + prompt

        # All three checkboxes - combine all behaviors
        if update_description and add_tasks and provide_answer:
            prompt = """You are a dev working on the current project. The client has sent in a message.

Read product-description.md and tasks.md.

Your job is to:
1. Update product-description.md based on the client's message
2. Add new tasks to tasks.md that reflect the updated description
3. Use the format `- [ ]` for new unchecked tasks
4. Provide a clear, helpful answer to the client in answer.md
5. The answer should acknowledge both the description update and tasks added

Client message:
{message}
""".format(message=message)
            return history_block + prompt

        # No checkboxes selected - send the user message directly as the prompt.
        return message

    @staticmethod
    def format_description_initialize_prompt(message: str) -> str:
        """Format the description initialization prompt."""
        return PromptTemplates.DESCRIPTION_INITIALIZE_PROMPT.format(message=message)

    @staticmethod
    def format_description_update_prompt(message: str) -> str:
        """Format the description update prompt."""
        return PromptTemplates.DESCRIPTION_UPDATE_PROMPT.format(message=message)

    @staticmethod
    def format_repository_description_bootstrap_prompt() -> str:
        """Format the prompt for generating initial description from existing repository."""
        return PromptTemplates.REPOSITORY_DESCRIPTION_BOOTSTRAP_PROMPT
