"""Prompt templates for all LLM interactions."""

from enum import Enum


class ReviewType(Enum):
    """Types of code review."""
    ARCHITECTURE = "architecture"
    EFFICIENCY = "efficiency"
    ERROR_HANDLING = "error_handling"
    SAFETY = "safety"
    TESTING = "testing"
    DOCUMENTATION = "documentation"


class PromptTemplates:
    """Central repository for all LLM prompt templates."""

    # =========================================================================
    # Phase 1: Question Generation
    # =========================================================================
    QUESTION_GENERATION = '''TASK: Create a questions.json file immediately.

PROJECT DESCRIPTION: {description}

IMMEDIATE ACTION REQUIRED:
1. Create a file called {working_directory}/questions.json
2. Write valid JSON with clarifying questions about this project

JSON FORMAT (use exactly this structure):
{{
  "questions": [
    {{"id": "q1", "question": "Your question here?", "options": ["Option 1", "Option 2", "Option 3"]}},
    {{"id": "q2", "question": "Another question?", "options": ["A", "B", "C", "D"]}}
  ]
}}

Generate 5-10 questions covering: platform, language/framework, scale, integrations, deployment, features, UI, data storage.

DO THIS NOW. Create the file immediately. Do not ask for clarification. Do not wait for input.'''

    # =========================================================================
    # Phase 2: Task Planning
    # =========================================================================
    TASK_PLANNING = '''You are a software architect creating a detailed implementation plan.

PROJECT DESCRIPTION:
{description}

USER ANSWERS TO CLARIFYING QUESTIONS:
{answers}

Create a comprehensive task list for implementing this project. Output ONLY a markdown checklist.

RULES:
1. Use `- [ ]` for each task (unchecked checkbox)
2. Order tasks by dependency (prerequisites first)
3. Be specific and actionable - each task should be completable in one coding session
4. Include setup, implementation, testing, and documentation tasks
5. Output ONLY the markdown task list, nothing else
6. Do not use nested tasks or sub-items
7. Each task should be self-contained

Example format:
- [ ] Initialize project structure with package.json and dependencies
- [ ] Create database models for User entity
- [ ] Implement user registration API endpoint
- [ ] Add input validation for registration
- [ ] Write unit tests for registration
- [ ] Create user login API endpoint
- [ ] Implement JWT token generation
- [ ] Add authentication middleware
- [ ] Write integration tests for auth flow
- [ ] Create README with setup instructions'''

    # =========================================================================
    # Phase 3: Main Execution
    # =========================================================================
    MAIN_EXECUTION = '''You are an autonomous code implementation agent working in the directory: {working_directory}

RECENT CHANGES (for context on what has been done):
{recent_changes}

CURRENT TASK LIST:
{tasks}

INSTRUCTIONS:
1. Read the recent changes to understand the current project state
2. Choose exactly ONE incomplete task from the task list (marked with `- [ ]`)
3. Implement that task completely and thoroughly
4. After implementing, update the recent-changes.md file with what you changed
5. Mark the task as complete in tasks.md by changing `- [ ]` to `- [x]`
6. If you discover additional tasks that need to be done, add them to tasks.md

CRITICAL RULES:
- Only work on ONE task per invocation
- Only remove ONE unchecked task per iteration (by marking it complete)
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
    }

    # =========================================================================
    # Phase 4: Fixer Prompt
    # =========================================================================
    FIXER = '''A code review has been performed for {review_type}.

REVIEW FINDINGS:
{review_content}

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

Run: `git push`

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
        ]

    @classmethod
    def format_question_prompt(cls, description: str, working_directory: str = ".") -> str:
        """Format the question generation prompt."""
        return cls.QUESTION_GENERATION.format(
            description=description,
            working_directory=working_directory
        )

    @classmethod
    def format_planning_prompt(cls, description: str, answers: dict) -> str:
        """Format the task planning prompt."""
        # Format answers as readable text
        answers_text = "\n".join(
            f"- {q_id}: {answer}" for q_id, answer in answers.items()
        )
        return cls.TASK_PLANNING.format(
            description=description,
            answers=answers_text
        )

    @classmethod
    def format_execution_prompt(cls, working_directory: str,
                                 recent_changes: str, tasks: str) -> str:
        """Format the main execution prompt."""
        return cls.MAIN_EXECUTION.format(
            working_directory=working_directory,
            recent_changes=recent_changes or "(No recent changes yet)",
            tasks=tasks
        )

    @classmethod
    def format_fixer_prompt(cls, review_type: str, review_content: str) -> str:
        """Format the fixer prompt."""
        return cls.FIXER.format(
            review_type=review_type,
            review_content=review_content
        )
