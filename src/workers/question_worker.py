"""Worker for Phase 1: Question Generation."""

import json
from pathlib import Path

from .base_worker import BaseWorker
from .llm_worker import LLMWorker
from ..llm.base_provider import LLMProviderRegistry
from ..llm.prompt_templates import PromptTemplates
from ..core.exceptions import LLMOutputParseError


class QuestionWorker(BaseWorker):
    """
    Phase 1 worker: Generates clarifying questions from user description.

    The LLM writes questions to questions.json file, which is then parsed.
    """

    MAX_PARSE_RETRIES = 2
    QUESTIONS_FILENAME = "questions.json"

    def __init__(self, description: str, provider_name: str = "gemini",
                 working_directory: str = None):
        super().__init__()
        self.description = description
        self.provider_name = provider_name
        self.working_directory = working_directory

    def execute(self):
        """Generate questions and return parsed JSON from questions.json file."""
        self.update_status("Generating clarifying questions...")
        self.log(f"=== QUESTION GENERATION PHASE START ===", "phase")
        self.log(f"Working directory: {self.working_directory}", "info")
        self.log(f"Project description: {self.description[:200]}{'...' if len(self.description) > 200 else ''}", "info")

        provider = LLMProviderRegistry.get(self.provider_name)
        self.log(f"Using LLM provider: {provider.display_name}", "info")

        # Build prompt - LLM will write to questions.json
        base_prompt = PromptTemplates.format_question_prompt(
            self.description,
            self.working_directory
        )
        prompt = provider.format_prompt(base_prompt, "freeform")
        self.log(f"Built question prompt ({len(prompt)} chars)", "debug")

        # Delete existing questions.json if present
        questions_path = Path(self.working_directory) / self.QUESTIONS_FILENAME
        if questions_path.exists():
            questions_path.unlink()
            self.log(f"Deleted existing {self.QUESTIONS_FILENAME}", "info")
        else:
            self.log(f"No existing {self.QUESTIONS_FILENAME} to delete", "debug")

        self.log(f"Expected output file: {questions_path}", "debug")

        last_error = None

        for attempt in range(1, self.MAX_PARSE_RETRIES + 1):
            self.check_cancelled()

            # Run LLM
            self.log(f"Calling {provider.display_name} for question generation (attempt {attempt}/{self.MAX_PARSE_RETRIES})...", "info")

            llm_worker = LLMWorker(
                provider=provider,
                prompt=prompt,
                working_directory=self.working_directory
            )

            # Forward LLM output signals
            llm_worker.signals.llm_output.connect(
                lambda line: self.signals.llm_output.emit(line)
            )
            # Forward log signals so command is visible
            llm_worker.signals.log.connect(
                lambda msg, level: self.signals.log.emit(msg, level)
            )

            # Run synchronously (we're already in a worker thread)
            llm_worker.run()

            # Get the result
            if llm_worker._is_cancelled:
                self.log(f"LLM worker was cancelled", "warning")
                self.check_cancelled()

            # Log the LLM output for debugging
            llm_output = ''.join(llm_worker._output_lines)
            if llm_output.strip():
                self.log(f"LLM output ({len(llm_output)} chars): {llm_output[:500]}{'...' if len(llm_output) > 500 else ''}", "info")
            else:
                self.log(f"LLM produced no output", "warning")

            # Log where we're looking for the file
            self.log(f"Looking for questions.json at: {questions_path}", "info")
            self.log(f"File exists: {questions_path.exists()}", "debug")

            # Try to read and parse questions.json
            try:
                questions = self._read_questions_file(questions_path)
                question_list = questions.get('questions', [])
                self.log(f"Generated {len(question_list)} questions", "success")

                # Log question summary
                for i, q in enumerate(question_list[:5], 1):
                    q_text = q.get('question', 'N/A')[:60]
                    opts = len(q.get('options', []))
                    self.log(f"  Q{i}: {q_text}{'...' if len(q.get('question', '')) > 60 else ''} ({opts} options)", "debug")
                if len(question_list) > 5:
                    self.log(f"  ... and {len(question_list) - 5} more questions", "debug")

                self.log(f"=== QUESTION GENERATION PHASE END ===", "phase")
                self.signals.questions_ready.emit(questions)
                return questions

            except LLMOutputParseError as e:
                last_error = e
                self.log(f"Failed to parse questions (attempt {attempt}): {e}", "warning")

                if attempt < self.MAX_PARSE_RETRIES:
                    self.log(f"Retrying with more explicit instructions...", "info")
                    # Add more explicit instruction for retry
                    prompt = provider.format_prompt(
                        f"{base_prompt}\n\n"
                        f"CRITICAL: The file {questions_path} was NOT created. "
                        f"You MUST create it NOW. Use your file writing tool to create {questions_path} with valid JSON.",
                        "freeform"
                    )

        self.log(f"All {self.MAX_PARSE_RETRIES} attempts failed to generate valid questions", "error")
        raise last_error or LLMOutputParseError("Failed to generate valid questions")

    def _read_questions_file(self, questions_path: Path) -> dict:
        """Read and parse the questions.json file."""
        self.log(f"Attempting to read {questions_path}", "debug")

        if not questions_path.exists():
            self.log(f"File not found: {questions_path}", "warning")
            raise LLMOutputParseError(f"{self.QUESTIONS_FILENAME} was not created by the LLM")

        try:
            content = questions_path.read_text(encoding="utf-8")
            self.log(f"Read {len(content)} chars from {self.QUESTIONS_FILENAME}", "debug")

            data = json.loads(content)
            self.log(f"Successfully parsed JSON", "debug")

            # Validate structure
            if "questions" not in data:
                self.log(f"JSON missing 'questions' key. Keys found: {list(data.keys())}", "warning")
                raise LLMOutputParseError("questions.json missing 'questions' key")

            if not isinstance(data["questions"], list):
                self.log(f"'questions' is not an array, got: {type(data['questions'])}", "warning")
                raise LLMOutputParseError("'questions' must be an array")

            self.log(f"JSON validation passed", "debug")
            return data

        except json.JSONDecodeError as e:
            self.log(f"JSON parse error at line {e.lineno}, col {e.colno}: {e.msg}", "warning")
            self.log(f"Content preview: {content[:200]}{'...' if len(content) > 200 else ''}", "debug")
            raise LLMOutputParseError(f"Invalid JSON in {self.QUESTIONS_FILENAME}: {e}")
