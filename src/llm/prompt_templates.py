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
    TASK_PLANNING = '''
I want you to make a task list in the tasks.md file.
Do not implement any code; only write the task list.
The tasks should be created according to the gap of what currently exists and what is in the product-description.md

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
2. Choose exactly ONE incomplete task from tasks.md list (marked with `- [ ]`)
3. Implement that task completely and thoroughly
4. After implementing, update the recent-changes.md file with what you changed
5. Mark the task as complete in tasks.md by changing `- [ ]` to `- [x]`
6. If you discover additional tasks that need to be done, add them to tasks.md but do not execute them

CRITICAL RULES:
- Only work on ONE task and complete it do not complete more than 1 task
- Only mark one task as complete once you have fully completed it
- Be thorough - the task should be fully complete before marking done
- Always update both tasks.md and recent-changes.md
'''

    MAIN_EXECUTION_MULTI = '''
INSTRUCTIONS:
1. Read the recent-changes.md
2. Choose up to {tasks_per_iteration} incomplete tasks from tasks.md list (marked with `- [ ]`)
3. Implement each chosen task completely and thoroughly
4. After implementing, update the recent-changes.md file with what you changed
5. Mark each completed task in tasks.md by changing `- [ ]` to `- [x]`
6. If you discover additional tasks that need to be done, add them to tasks.md but do not execute them

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
