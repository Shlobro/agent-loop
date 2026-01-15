"""Worker for Phase 1: Question Generation."""

import json
import re
from pathlib import Path
from typing import List, Dict

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
                 working_directory: str = None, model: str = None):
        super().__init__()
        self.description = description
        self.provider_name = provider_name
        self.working_directory = working_directory
        self.model = model

    def execute(self):
        """Generate questions and return parsed JSON from questions.json file."""
        self.update_status("Generating clarifying questions...")
        self.log(f"=== QUESTION GENERATION PHASE START ===", "phase")
        self.log(f"Working directory: {self.working_directory}", "info")
        self.log(f"Project description: {self.description[:200]}{'...' if len(self.description) > 200 else ''}", "info")

        provider = LLMProviderRegistry.get(self.provider_name)
        self.log(f"Using LLM provider: {provider.display_name}", "info")

        # Build prompt - LLM will output JSON to stdout
        base_prompt = PromptTemplates.format_question_prompt(
            self.description,
            self.working_directory
        )
        prompt = provider.format_prompt(base_prompt, "json")
        self.log(f"Built question prompt ({len(prompt)} chars)", "debug")

        last_error = None

        for attempt in range(1, self.MAX_PARSE_RETRIES + 1):
            self.check_cancelled()

            # Run LLM
            self.log(f"Calling {provider.display_name} for question generation (attempt {attempt}/{self.MAX_PARSE_RETRIES})...", "info")

            llm_worker = LLMWorker(
                provider=provider,
                prompt=prompt,
                working_directory=self.working_directory,
                model=self.model
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

            # Parse the LLM output directly as JSON
            llm_output = ''.join(llm_worker._output_lines)
            if llm_output.strip():
                self.log(f"LLM output ({len(llm_output)} chars): {llm_output[:500]}{'...' if len(llm_output) > 500 else ''}", "info")
            else:
                self.log(f"LLM produced no output", "warning")

            # Try to parse JSON directly from output
            try:
                questions = self._parse_json_output(llm_output)
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
                        f"CRITICAL: Your previous output was not valid JSON. "
                        f"Output ONLY valid JSON starting with {{ and ending with }}. "
                        f"No explanatory text. No markdown fences. Just the JSON.",
                        "json"
                    )

        self.log(f"All {self.MAX_PARSE_RETRIES} attempts failed to generate valid questions", "error")
        raise last_error or LLMOutputParseError("Failed to generate valid questions")

    def _parse_json_output(self, output: str) -> dict:
        """Parse JSON directly from LLM output."""
        self.log(f"Attempting to parse JSON from output", "debug")

        # Strip any markdown code fences
        output = output.strip()
        if output.startswith("```json"):
            output = output[7:]
        if output.startswith("```"):
            output = output[3:]
        if output.endswith("```"):
            output = output[:-3]
        output = output.strip()

        # Find JSON object boundaries
        start_idx = output.find('{')
        end_idx = output.rfind('}')

        if start_idx == -1 or end_idx == -1:
            self.log(f"No JSON object found in output", "warning")
            raise LLMOutputParseError("No JSON object found in LLM output")

        json_str = output[start_idx:end_idx+1]
        self.log(f"Extracted JSON substring ({len(json_str)} chars)", "debug")

        try:
            data = json.loads(json_str)
            self.log(f"Successfully parsed JSON", "debug")

            # Validate structure
            if "questions" not in data:
                self.log(f"JSON missing 'questions' key. Keys found: {list(data.keys())}", "warning")
                raise LLMOutputParseError("JSON output missing 'questions' key")

            if not isinstance(data["questions"], list):
                self.log(f"'questions' is not an array, got: {type(data['questions'])}", "warning")
                raise LLMOutputParseError("'questions' must be an array")

            if len(data["questions"]) == 0:
                self.log(f"'questions' array is empty", "warning")
                raise LLMOutputParseError("'questions' array is empty")

            self.log(f"JSON validation passed", "debug")

            # Now write the parsed JSON to the file for compatibility
            questions_path = Path(self.working_directory) / self.QUESTIONS_FILENAME
            questions_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            self.log(f"Wrote parsed JSON to {self.QUESTIONS_FILENAME}", "debug")

            return data

        except json.JSONDecodeError as e:
            self.log(f"JSON parse error at line {e.lineno}, col {e.colno}: {e.msg}", "warning")
            self.log(f"JSON substring: {json_str[:200]}{'...' if len(json_str) > 200 else ''}", "debug")
            raise LLMOutputParseError(f"Invalid JSON in LLM output: {e}")


class SingleQuestionWorker(BaseWorker):
    """
    Phase 1 worker: Generates a single clarifying question from user description
    and prior Q&A pairs.
    """

    MAX_PARSE_RETRIES = 2
    QUESTION_FILENAME = "single_question.json"

    def __init__(self, description: str, previous_qa: List[Dict[str, str]],
                 provider_name: str = "gemini", working_directory: str = None,
                 model: str = None):
        super().__init__()
        self.description = description
        self.previous_qa = previous_qa or []
        self.provider_name = provider_name
        self.working_directory = working_directory
        self.model = model

    def execute(self):
        """Generate one question and return parsed JSON from single_question.json file."""
        self.update_status("Generating clarifying question...")
        self.log("=== SINGLE QUESTION GENERATION START ===", "phase")
        self.log(f"Working directory: {self.working_directory}", "info")
        self.log(f"Project description: {self.description[:200]}{'...' if len(self.description) > 200 else ''}", "info")
        self.log(f"Previous Q&A count: {len(self.previous_qa)}", "info")

        provider = LLMProviderRegistry.get(self.provider_name)
        self.log(f"Using LLM provider: {provider.display_name}", "info")

        base_prompt = PromptTemplates.format_single_question_prompt(
            self.description,
            self.previous_qa,
            self.working_directory
        )
        prompt = provider.format_prompt(base_prompt, "json")
        self.log(f"Built single question prompt ({len(prompt)} chars)", "debug")

        last_error = None

        for attempt in range(1, self.MAX_PARSE_RETRIES + 1):
            self.check_cancelled()

            self.log(
                f"Calling {provider.display_name} for single question (attempt {attempt}/{self.MAX_PARSE_RETRIES})...",
                "info"
            )

            llm_worker = LLMWorker(
                provider=provider,
                prompt=prompt,
                working_directory=self.working_directory,
                model=self.model
            )

            llm_worker.signals.llm_output.connect(
                lambda line: self.signals.llm_output.emit(line)
            )
            llm_worker.signals.log.connect(
                lambda msg, level: self.signals.log.emit(msg, level)
            )

            llm_worker.run()

            if llm_worker._is_cancelled:
                self.log("LLM worker was cancelled", "warning")
                self.check_cancelled()

            llm_output = ''.join(llm_worker._output_lines)
            if llm_output.strip():
                self.log(f"LLM output ({len(llm_output)} chars): {llm_output[:500]}{'...' if len(llm_output) > 500 else ''}", "info")
            else:
                self.log("LLM produced no output", "warning")

            try:
                question_data = self._parse_single_question_output(llm_output)
                self.log("Generated single question successfully", "success")
                self.log(f"Question: {question_data.get('question', '')[:80]}", "debug")
                self.log(f"Options: {len(question_data.get('options', []))}", "debug")

                self.log("=== SINGLE QUESTION GENERATION END ===", "phase")
                self.signals.single_question_ready.emit(question_data)
                return question_data

            except LLMOutputParseError as e:
                last_error = e
                self.log(f"Failed to parse single question (attempt {attempt}): {e}", "warning")

                if attempt < self.MAX_PARSE_RETRIES:
                    self.log("Retrying with more explicit instructions...", "info")
                    prompt = provider.format_prompt(
                        f"{base_prompt}\n\n"
                        f"CRITICAL: Your previous output was not valid JSON. "
                        f"Output ONLY valid JSON starting with {{ and ending with }}. "
                        f"No explanatory text. No markdown fences. Just the JSON.",
                        "json"
                    )

        self.log(f"All {self.MAX_PARSE_RETRIES} attempts failed to generate valid question", "error")
        raise last_error or LLMOutputParseError("Failed to generate valid single question")

    def _parse_single_question_output(self, output: str) -> dict:
        """Parse JSON directly from LLM output."""
        self.log(f"Attempting to parse JSON from output", "debug")

        # Strip any markdown code fences
        output = output.strip()
        if output.startswith("```json"):
            output = output[7:]
        if output.startswith("```"):
            output = output[3:]
        if output.endswith("```"):
            output = output[:-3]
        output = output.strip()

        # Find JSON object boundaries
        start_idx = output.find('{')
        end_idx = output.rfind('}')

        if start_idx == -1 or end_idx == -1:
            self.log(f"No JSON object found in output", "warning")
            raise LLMOutputParseError("No JSON object found in LLM output")

        json_str = output[start_idx:end_idx+1]
        self.log(f"Extracted JSON substring ({len(json_str)} chars)", "debug")

        try:
            data = json.loads(json_str)
            if not isinstance(data, dict):
                raise LLMOutputParseError("Output must be a JSON object")

            question = data.get("question") or data.get("text") or data.get("prompt")
            if not question:
                self.log(f"JSON keys found: {list(data.keys())}", "warning")
                raise LLMOutputParseError("JSON output missing 'question' key")

            options = data.get("options") or data.get("choices") or data.get("answers")
            options_list = self._normalize_options(options)

            if len(options_list) == 0:
                self.log(f"Options field was: {options}", "warning")
                raise LLMOutputParseError("'options' array is empty or missing")

            result = {
                "question": str(question).strip(),
                "options": options_list
            }

            self.log(f"JSON validation passed", "debug")

            # Write to file for compatibility
            question_path = Path(self.working_directory) / self.QUESTION_FILENAME
            question_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
            self.log(f"Wrote parsed JSON to {self.QUESTION_FILENAME}", "debug")

            return result

        except json.JSONDecodeError as e:
            self.log(f"JSON parse error at line {e.lineno}, col {e.colno}: {e.msg}", "warning")
            self.log(f"JSON substring: {json_str[:200]}{'...' if len(json_str) > 200 else ''}", "debug")
            raise LLMOutputParseError(f"Invalid JSON in LLM output: {e}")

    def _normalize_options(self, options: object) -> List[str]:
        """Normalize options to a list of non-empty strings."""
        if options is None:
            return []
        if isinstance(options, list):
            return [str(option).strip() for option in options if str(option).strip()]
        if isinstance(options, dict):
            return [str(option).strip() for option in options.values() if str(option).strip()]
        if isinstance(options, str):
            stripped = options.strip()
            if not stripped:
                return []
            parts = re.split(r"[,\n\r|/;]", stripped)
            return [part.strip() for part in parts if part.strip()]
        return []
