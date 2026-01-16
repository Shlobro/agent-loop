"""Prompt templates for all LLM interactions."""

from enum import Enum
from typing import Union


class ReviewType(Enum):
    """Types of code review."""
    ARCHITECTURE = "architecture"
    EFFICIENCY = "efficiency"
    ERROR_HANDLING = "error_handling"
    SAFETY = "safety"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    UI_UX = "ui_ux"


class PromptTemplates:
    """Central repository for all LLM prompt templates."""

    # =========================================================================
    # Phase 1: Question Generation (Batch mode)
    # =========================================================================
    QUESTION_GENERATION_PROMPT = (
        'your job is to edit `questions.json` file with {question_count} questions to clarify '
        'exactly what the user wants to make. provide the user with 3-5 possible '
        'answers for each question. the format of the json should be '
        '{{"questions":[{{"question":"...","options":["...","..."]}}]}}.\n\n'
        'there already exists an empty questions.json file. edit it and put the questions there. '
        'Write the JSON to `questions.json` in the working directory: {working_directory}. '
        'Do not implement any code I only want the clarifying questions in the `questions.json` file. '
        'Do not create any new files, only edit the existing questions.json with new questions and answers. '
        'in the project description the user inputted was: "{description}".'
    )

    # =========================================================================
    # Question Follow-up: Q&A -> Product Definition Rewrite
    # =========================================================================
    DEFINITION_REWRITE_PROMPT = '''edit description.md or make it if it does not exist Rewrite the project description into a clear product definition using the original description and the clarifying Q&A.

ORIGINAL DESCRIPTION:
{description}

CLARIFYING QUESTIONS AND ANSWERS:
{answers}

- Output a concise product definition in markdown.
- Do NOT include the Q&A format or questions.
- Do NOT write code or edit any files except the description.md.
- Write the product definition to `description.md` in the working directory: {working_directory}.
'''


    # =========================================================================
    # Phase 2: Task Planning
    # =========================================================================
    TASK_PLANNING = '''You are a software architect creating a detailed implementation plan.

PROJECT DESCRIPTION:
{description}

USER ANSWERS TO CLARIFYING QUESTIONS:
{answers}

OUTPUT REQUIREMENTS - READ CAREFULLY:
Your response MUST be ONLY a markdown checklist. Do NOT include any introductory text, explanations, or commentary.
Do NOT say "I'll help" or "Here's the plan" or anything similar.
Your FIRST character must be a dash (-).

TASK LIST RULES:
1. Use `- [ ]` for each task (unchecked checkbox)
2. Order tasks by dependency (prerequisites first)
3. Be specific and actionable - each task should be completable in one coding session
4. Include setup, implementation, testing, and documentation tasks
5. Do not use nested tasks or sub-items
6. Each task should be self-contained
7. Create 10-30 tasks depending on project complexity

CORRECT OUTPUT FORMAT (start immediately with tasks):
- [ ] Initialize project structure with package.json and dependencies
- [ ] Create database models for User entity
- [ ] Implement user registration API endpoint
- [ ] Add input validation for registration
- [ ] Write unit tests for registration
- [ ] Create user login API endpoint
- [ ] Implement JWT token generation
- [ ] Add authentication middleware
- [ ] Write integration tests for auth flow
- [ ] Create README with setup instructions

BEGIN YOUR OUTPUT NOW (first character must be `-`):'''

    # =========================================================================
    # Description Generation (for description.md)
    # =========================================================================
    DESCRIPTION_GENERATION = '''Create a comprehensive project description document based on the user's input and clarifying questions.

PROJECT OBJECTIVE:
{description}

USER ANSWERS TO CLARIFYING QUESTIONS:
{answers}

OUTPUT REQUIREMENTS:
Create a well-structured markdown document that summarizes the complete project specification.
This document will be used by developers to understand the project goals and requirements.

Include these sections:
1. Project Overview - High-level description of what's being built
2. Technical Stack - Languages, frameworks, databases, and tools to be used
3. Key Features - List of main features and functionality
4. Architecture - Brief architectural approach
5. Requirements - Specific technical and functional requirements

Use markdown formatting with headers (##), lists, and emphasis where appropriate.
Be comprehensive but concise. Focus on actionable information that helps with implementation.

BEGIN YOUR OUTPUT NOW:'''

    # =========================================================================
    # Phase 3: Main Execution
    # =========================================================================
    MAIN_EXECUTION = '''You are an autonomous code implementation agent working in the directory: {working_directory}

RECENT CHANGES (for context on what has been done):
{recent_changes}

CURRENT TASK LIST:
{tasks}

WORKSPACE GOVERNANCE RULES (must always follow):
- Every folder (including the root and any new folder) must contain exactly one developer guide `.md` file, except ignored system/tooling directories like `.git`, `.venv`, `.idea`, `.claude`, and `node_modules`.
- Before editing files in a folder, read its developer guide `.md` file.
- Update the folder's guide and all ancestor folder guides if changes affect developer understanding.
- No code file may exceed 1000 lines; split files when near the limit.
- No folder may contain more than 10 files; create subfolders to reduce file counts.

CURRENT WORKSPACE COMPLIANCE CHECK:
{compliance_report}

INSTRUCTIONS:
1. Read the recent changes to understand the current project state
2. Choose exactly ONE incomplete task from the task list (marked with `- [ ]`)
3. Implement that task completely and thoroughly
4. After implementing, update the recent-changes.md file with what you changed
5. Mark the task as complete in tasks.md by changing `- [ ]` to `- [x]`
6. If you discover additional tasks that need to be done, add them to tasks.md but do not execute them

CRITICAL RULES:
- Only work on ONE task and complete it do not complete more than 1 task
- Only mark one task as complete once you have fully completed it
- Be thorough - the task should be fully complete before marking done
- If you cannot complete a task, leave it unchecked and explain in recent-changes.md
- Always update both tasks.md and recent-changes.md'''

    # =========================================================================
    # Phase 4: Review Prompts
    # =========================================================================
    REVIEW_PROMPTS = {
        ReviewType.ARCHITECTURE: '''Review the recent code changes for ARCHITECTURAL concerns.

Use `git diff` to see the recent changes in the working directory.

Evaluate:
- Code organization and module structure
- Separation of concerns (is each module doing one thing?)
- Design patterns usage (are appropriate patterns used?)
- Coupling and cohesion (are dependencies well-managed?)
- Scalability considerations
- Code reusability

Write your findings to review.md in this format:
```review
## Architecture Review

### Issues Found:
1. [Issue description]
   - File: [filename]
   - Line: [line number if applicable]
   - Severity: [High/Medium/Low]
   - Suggestion: [How to fix]

### Positive Observations:
- [What's done well]
```

If no issues found, write "No architectural issues found."''',

        ReviewType.EFFICIENCY: '''Review the recent code changes for EFFICIENCY concerns.

Use `git diff` to see the recent changes in the working directory.

Evaluate:
- Algorithm complexity (O(n) considerations)
- Unnecessary computations or redundant operations
- Memory usage and potential leaks
- Database query efficiency (N+1 problems)
- Caching opportunities
- Resource cleanup

Write your findings to review.md in this format:
```review
## Efficiency Review

### Issues Found:
1. [Issue description]
   - File: [filename]
   - Line: [line number if applicable]
   - Severity: [High/Medium/Low]
   - Suggestion: [How to fix]

### Positive Observations:
- [What's done well]
```

If no issues found, write "No efficiency issues found."''',

        ReviewType.ERROR_HANDLING: '''Review the recent code changes for ERROR HANDLING concerns.

Use `git diff` to see the recent changes in the working directory.

Evaluate:
- Exception handling coverage (are errors caught appropriately?)
- Error message clarity (can users understand what went wrong?)
- Recovery mechanisms (does the code fail gracefully?)
- Edge case handling (null checks, empty arrays, etc.)
- Logging of errors for debugging
- Proper error propagation

Write your findings to review.md in this format:
```review
## Error Handling Review

### Issues Found:
1. [Issue description]
   - File: [filename]
   - Line: [line number if applicable]
   - Severity: [High/Medium/Low]
   - Suggestion: [How to fix]

### Positive Observations:
- [What's done well]
```

If no issues found, write "No error handling issues found."''',

        ReviewType.SAFETY: '''Review the recent code changes for SAFETY and SECURITY concerns.

Use `git diff` to see the recent changes in the working directory.

Evaluate:
- Input validation (is user input sanitized?)
- SQL injection vulnerabilities
- XSS (Cross-Site Scripting) vulnerabilities
- Sensitive data exposure (passwords, API keys, tokens)
- Authentication/authorization checks
- CSRF protection
- Secure communication (HTTPS, encryption)
- File upload security

Write your findings to review.md in this format:
```review
## Safety/Security Review

### Issues Found:
1. [Issue description]
   - File: [filename]
   - Line: [line number if applicable]
   - Severity: [Critical/High/Medium/Low]
   - Suggestion: [How to fix]

### Positive Observations:
- [What's done well]
```

If no issues found, write "No security issues found."''',

        ReviewType.TESTING: '''Review the recent code changes for TESTING concerns.

Use `git diff` to see the recent changes in the working directory.

Evaluate:
- Test coverage (are new functions/methods tested?)
- Test quality (do tests actually verify behavior?)
- Missing test cases (edge cases, error paths)
- Test organization and naming
- Mock usage (are external dependencies mocked?)
- Integration test coverage

Write your findings to review.md in this format:
```review
## Testing Review

### Issues Found:
1. [Issue description]
   - File: [filename]
   - Line: [line number if applicable]
   - Severity: [High/Medium/Low]
   - Suggestion: [How to fix]

### Missing Tests:
- [What should be tested]

### Positive Observations:
- [What's done well]
```

If no issues found, write "No testing issues found."''',

        ReviewType.DOCUMENTATION: '''Review the recent code changes for DOCUMENTATION concerns.

Use `git diff` to see the recent changes in the working directory.

Evaluate:
- Code comments (are complex sections explained?)
- Docstrings/JSDoc (are public functions documented?)
- README completeness (setup, usage, examples)
- API documentation
- Inline documentation for non-obvious code
- Type hints/annotations

Write your findings to review.md in this format:
```review
## Documentation Review

### Issues Found:
1. [Issue description]
   - File: [filename]
   - Line: [line number if applicable]
   - Severity: [High/Medium/Low]
   - Suggestion: [How to fix]

### Positive Observations:
- [What's done well]
```

If no issues found, write "No documentation issues found."''',

        ReviewType.UI_UX: '''Review the recent code changes for UI/UX concerns.

Use `git diff` to see the recent changes in the working directory.

Evaluate:
- User flows and task clarity
- Visual hierarchy and layout consistency
- Text clarity and microcopy
- Accessibility (contrast, focus states, keyboard navigation)
- Responsiveness (small/large window sizes)
- UI state feedback (loading, empty, error states)

Write your findings to review.md in this format:
```review
## UI/UX Review

### Issues Found:
1. [Issue description]
   - File: [filename]
   - Line: [line number if applicable]
   - Severity: [High/Medium/Low]
   - Suggestion: [How to fix]

### Positive Observations:
- [What's done well]
```

If no issues found, write "No UI/UX issues found."''',
    }

    # =========================================================================
    # Phase 4: Fixer Prompt
    # =========================================================================
    FIXER = '''A code review has been performed for {review_type}.

REVIEW FINDINGS:
{review_content}

WORKSPACE GOVERNANCE RULES (must always follow):
- Every folder (including the root and any new folder) must contain exactly one developer guide `.md` file, except ignored system/tooling directories like `.git`, `.venv`, `.idea`, `.claude`, and `node_modules`.
- Before editing files in a folder, read its developer guide `.md` file.
- Update the folder's guide and all ancestor folder guides if changes affect developer understanding.
- No code file may exceed 1000 lines; split files when near the limit.
- No folder may contain more than 10 files; create subfolders to reduce file counts.

CURRENT WORKSPACE COMPLIANCE CHECK:
{compliance_report}

Your task:
1. Read each issue found in the review
2. For each issue, decide: Do you AGREE or DISAGREE?
3. For issues you AGREE with: Implement the fix
4. For issues you DISAGREE with: Briefly explain why in recent-changes.md

After making changes:
1. Update recent-changes.md with what you fixed
2. If you disagreed with any findings, explain your reasoning

Be practical - only fix issues that genuinely improve the code.'''

    # =========================================================================
    # Phase 5: Git Operations
    # =========================================================================
    GIT_COMMIT = '''Perform git operations to commit the recent changes.

1. Run `git add .` to stage all changes
2. Create a meaningful commit message that summarizes the work done
3. Run `git commit -m "your message"`

Commit message should:
- Start with a verb (Add, Fix, Update, Implement, etc.)
- Be concise but descriptive
- Reference the main feature or fix

Example: "Implement user authentication with JWT tokens"'''

    GIT_PUSH = '''Push the committed changes to the remote repository.

{remote_setup}Run: `git push -u origin HEAD`

If push fails due to remote changes, do NOT force push.
Instead, report the error and suggest the user resolve it manually.'''

    @classmethod
    def get_review_prompt(cls, review_type: ReviewType) -> str:
        """Get the review prompt for a specific review type."""
        return cls.REVIEW_PROMPTS.get(review_type, "")

    @classmethod
    def get_all_review_types(cls) -> list:
        """Get list of all review types in order."""
        return [
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
    def format_question_prompt(cls, description: str, question_count: int,
                               previous_qa: list, working_directory: str = ".") -> str:
        """Format the question generation prompt (batch mode)."""
        return cls.QUESTION_GENERATION_PROMPT.format(
            description=description,
            question_count=question_count,
            working_directory=working_directory
        )

    @classmethod
    def format_description_prompt(cls, description: str, answers: dict,
                                   qa_pairs: list = None) -> str:
        """Format the description.md generation prompt.

        Args:
            description: The project description
            answers: Dict of {question_id: answer} (legacy format)
            qa_pairs: List of {"question": ..., "answer": ...} (new format, preferred)
        """
        # Prefer qa_pairs if available (new iterative format)
        if qa_pairs:
            qa_lines = []
            for i, qa in enumerate(qa_pairs, 1):
                qa_lines.append(f"Q{i}: {qa['question']}")
                qa_lines.append(f"A{i}: {qa['answer']}")
                qa_lines.append("")
            answers_text = "\n".join(qa_lines)
        else:
            # Legacy format - just question IDs
            answers_text = "\n".join(
                f"- {q_id}: {answer}" for q_id, answer in answers.items()
            )
        return cls.DESCRIPTION_GENERATION.format(
            description=description,
            answers=answers_text
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
                                qa_pairs: list = None) -> str:
        """Format the task planning prompt.

        Args:
            description: The project description
            answers: Dict of {question_id: answer} (legacy format)
            qa_pairs: List of {"question": ..., "answer": ...} (new format, preferred)
        """
        # Prefer qa_pairs if available (new iterative format)
        if qa_pairs:
            qa_lines = []
            for i, qa in enumerate(qa_pairs, 1):
                qa_lines.append(f"Q{i}: {qa['question']}")
                qa_lines.append(f"A{i}: {qa['answer']}")
                qa_lines.append("")
            answers_text = "\n".join(qa_lines)
        else:
            # Legacy format - just question IDs
            answers_text = "\n".join(
                f"- {q_id}: {answer}" for q_id, answer in answers.items()
            )
        return cls.TASK_PLANNING.format(
            description=description,
            answers=answers_text
        )

    @classmethod
    def format_execution_prompt(cls, working_directory: str,
                                 recent_changes: str, tasks: str,
                                 compliance_report: str) -> str:
        """Format the main execution prompt with workspace rule context."""
        return cls.MAIN_EXECUTION.format(
            working_directory=working_directory,
            recent_changes=recent_changes or "(No recent changes yet)",
            tasks=tasks,
            compliance_report=compliance_report
        )

    @classmethod
    def format_fixer_prompt(cls, review_type: str,
                             review_content: str,
                             compliance_report: str) -> str:
        """Format the fixer prompt with workspace rule context."""
        return cls.FIXER.format(
            review_type=review_type,
            review_content=review_content,
            compliance_report=compliance_report
        )

    @classmethod
    def format_git_push_prompt(cls, git_remote: str = "") -> str:
        """Format the git push prompt with optional remote setup."""
        if git_remote:
            remote_setup = f'''First, set up the remote (if not already configured):
1. Check if origin exists: `git remote -v`
2. If origin doesn't exist, add it: `git remote add origin {git_remote}`
3. If origin exists but points elsewhere, update it: `git remote set-url origin {git_remote}`

'''
        else:
            remote_setup = ""
        return cls.GIT_PUSH.format(remote_setup=remote_setup)
