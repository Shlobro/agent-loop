"""Gemini CLI provider implementation."""

from typing import List
from .base_provider import BaseLLMProvider, LLMProviderRegistry


class GeminiProvider(BaseLLMProvider):
    """
    Gemini CLI provider using `gemini` command with --yolo flag.

    Uses stdin to pass the prompt to avoid shell escaping issues.
    """

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def display_name(self) -> str:
        return "Gemini"

    @property
    def uses_stdin(self) -> bool:
        """Gemini accepts prompt via stdin to avoid escaping issues."""
        return True

    def build_command(self, prompt: str) -> List[str]:
        """Build gemini CLI command.

        The prompt will be passed via stdin by the LLMWorker.
        """
        return ["gemini", "--yolo"]

    def get_stdin_prompt(self, prompt: str) -> str:
        """Return the prompt to send via stdin."""
        return prompt

    def get_output_instruction(self, output_type: str) -> str:
        """Return format instruction for Gemini."""
        instructions = {
            "json": (
                "IMPORTANT: Respond with valid JSON only. "
                "Do not include markdown code fences. "
                "Do not include any explanatory text before or after the JSON. "
                "The response must start with { and end with }."
            ),
            "markdown_tasks": (
                "IMPORTANT: Respond with a markdown task list only. "
                "Use `- [ ]` for incomplete tasks and `- [x]` for completed tasks. "
                "Do not include any other text or explanations."
            ),
            "review": (
                "Write your review findings inside ```review ... ``` code blocks. "
                "Be specific about file locations and line numbers when possible."
            ),
            "freeform": "",
        }
        return instructions.get(output_type, "")

    def get_setup_instructions(self) -> str:
        return (
            "Gemini CLI should be installed and configured with API credentials.\n"
            "The --yolo flag enables autonomous operation."
        )


# Register the provider
LLMProviderRegistry.register(GeminiProvider())
