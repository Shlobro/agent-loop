"""Worker for Phase 1: Question Generation."""

import json
from pathlib import Path
from typing import List, Dict

from .base_worker import BaseWorker
from .llm_worker import LLMWorker
from ..llm.base_provider import LLMProviderRegistry
from ..llm.prompt_templates import PromptTemplates
from ..core.exceptions import LLMOutputParseError
from ..utils.json_parser import parse_questions_json


class QuestionWorker(BaseWorker):
    """
    Phase 1 worker: Generates clarifying questions from user description.

    The LLM writes questions to questions.json file, which is then parsed.
    """

    QUESTIONS_FILENAME = "questions.json"
    DESCRIPTION_FILENAME = "product-description.md"

    def __init__(self, description: str, question_count: int,
                 previous_qa: List[Dict[str, str]] | None = None,
                 provider_name: str = "gemini", working_directory: str = None,
                 model: str = None):
        super().__init__()
        self.description = description
        self.question_count = question_count
        self.previous_qa = previous_qa or []
        self.provider_name = provider_name
        self.working_directory = working_directory
        self.model = model

    def execute(self):
        """Generate questions and return parsed JSON from questions.json file."""
        self.update_status("Generating clarifying questions...")
        self.log(f"=== QUESTION GENERATION PHASE START ===", "phase")
        self.log(f"Working directory: {self.working_directory}", "info")
        self.log(f"Project description: {self.description[:200]}{'...' if len(self.description) > 200 else ''}", "info")
        self.log(f"Question count: {self.question_count}", "info")
        self.log(f"Previous Q&A count: {len(self.previous_qa)}", "info")

        provider = LLMProviderRegistry.get(self.provider_name)
        self.log(f"Using LLM provider: {provider.display_name}", "info")

        # Build prompt - LLM writes JSON to file when possible, stdout otherwise
        base_prompt = PromptTemplates.format_question_prompt(
            description=self.description,
            question_count=self.question_count,
            previous_qa=self.previous_qa,
            working_directory=self.working_directory
        )
        output_type = "freeform" if provider.name == "codex" else "json"
        prompt = provider.format_prompt(base_prompt, output_type)
        self.log(f"Built question prompt ({len(prompt)} chars)", "debug")

        self.check_cancelled()

        # Run LLM once
        self.log(f"Calling {provider.display_name} for question generation...", "info")

        llm_worker = LLMWorker(
            provider=provider,
            prompt=prompt,
            working_directory=self.working_directory,
            model=self.model,
            debug_stage="question_generation"
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

        if llm_worker._is_cancelled:
            self.log("LLM worker was cancelled", "warning")
            self.check_cancelled()

        llm_output = ''.join(llm_worker._output_lines)
        if llm_output.strip():
            self.log(f"LLM output ({len(llm_output)} chars): {llm_output[:500]}{'...' if len(llm_output) > 500 else ''}", "info")
            self.log(f"LLM full output:\n{llm_output}", "info")
        else:
            self.log("LLM produced no output", "warning")

        try:
            questions = self._load_questions_file()
            questions = self._ensure_question_count(questions)
            question_list = questions.get("questions", [])
            self.log(f"Loaded {len(question_list)} questions from {self.QUESTIONS_FILENAME}", "success")
            self.log("=== QUESTION GENERATION PHASE END ===", "phase")
            self.signals.questions_ready.emit(questions)
            return questions
        except LLMOutputParseError as e:
            self.log(f"Question generation failed: {e}", "error")
            raise

    def _load_questions_file(self) -> dict:
        """Load questions from questions.json if present."""
        questions_path = Path(self.working_directory) / self.QUESTIONS_FILENAME
        if not questions_path.exists():
            raise LLMOutputParseError(f"{self.QUESTIONS_FILENAME} not found")
        try:
            content = questions_path.read_text(encoding="utf-8")
        except OSError as e:
            raise LLMOutputParseError(f"Failed to read {self.QUESTIONS_FILENAME}: {e}")

        return parse_questions_json(content)

    def _ensure_question_count(self, questions: dict) -> dict:
        """Ensure the questions list matches the requested count."""
        question_list = questions.get("questions", [])
        if len(question_list) < self.question_count:
            raise LLMOutputParseError(
                f"Expected {self.question_count} questions, got {len(question_list)}"
            )
        if len(question_list) > self.question_count:
            self.log(
                f"Trimmed questions from {len(question_list)} to {self.question_count}",
                "warning"
            )
            questions = {**questions, "questions": question_list[:self.question_count]}
            questions_path = Path(self.working_directory) / self.QUESTIONS_FILENAME
            questions_path.write_text(json.dumps(questions, indent=2), encoding="utf-8")
        return questions


class DefinitionRewriteWorker(BaseWorker):
    """
    Rewrite the project description into a product definition using Q&A context.
    """

    DESCRIPTION_FILENAME = "product-description.md"

    def __init__(self, description: str, qa_pairs: List[Dict[str, str]],
                 provider_name: str = "gemini", working_directory: str = None,
                 model: str = None):
        super().__init__()
        self.description = description
        self.qa_pairs = qa_pairs or []
        self.provider_name = provider_name
        self.working_directory = working_directory
        self.model = model

    def execute(self) -> str:
        """Generate a rewritten product definition from description and Q&A.

        The LLM must write the final content directly to product-description.md.
        """
        self.update_status("Refining product definition...")
        self.log("=== DEFINITION REWRITE START ===", "phase")
        self.log(f"Working directory: {self.working_directory}", "info")
        self.log(f"Q&A pairs: {len(self.qa_pairs)}", "info")

        if not self.qa_pairs:
            self.log("No Q&A pairs provided; using original description", "warning")
            return self.description

        provider = LLMProviderRegistry.get(self.provider_name)
        self.log(f"Using LLM provider: {provider.display_name}", "info")

        base_prompt = PromptTemplates.format_definition_rewrite_prompt(
            description=self.description,
            qa_pairs=self.qa_pairs,
            working_directory=self.working_directory or "."
        )
        prompt = provider.format_prompt(base_prompt, "freeform")
        self.log(f"Built definition rewrite prompt ({len(prompt)} chars)", "debug")

        llm_worker = LLMWorker(
            provider=provider,
            prompt=prompt,
            working_directory=self.working_directory,
            model=self.model,
            debug_stage="description_molding"
        )
        llm_worker.signals.llm_output.connect(
            lambda line: self.signals.llm_output.emit(line)
        )
        llm_worker.signals.log.connect(
            lambda msg, level: self.signals.log.emit(msg, level)
        )

        try:
            llm_worker.run()
        except Exception as exc:
            self.log(f"Definition rewrite failed: {exc}", "warning")
            return self.description

        rewritten = self._load_definition_file()
        if rewritten:
            self.log("Loaded rewritten description from product-description.md", "success")
            self.log("=== DEFINITION REWRITE END ===", "phase")
            return rewritten

        self.log(
            "Definition rewrite did not update product-description.md; ignoring stdout and keeping original description",
            "warning"
        )
        return self.description

    def _load_definition_file(self) -> str:
        if not self.working_directory:
            return ""
        path = Path(self.working_directory) / self.DESCRIPTION_FILENAME
        if not path.exists():
            return ""
        try:
            content = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            self.log(f"Failed to read product-description.md: {exc}", "warning")
            return ""
        return content

