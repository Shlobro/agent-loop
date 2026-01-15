"""Codex CLI provider implementation."""

from typing import List
from .base_provider import BaseLLMProvider, LLMProviderRegistry


class CodexProvider(BaseLLMProvider):
    """
    Codex CLI provider using `codex exec --full-auto` command.
    """

    @property
    def name(self) -> str:
        return "codex"

    @property
    def display_name(self) -> str:
        return "Codex"

    def build_command(self, prompt: str) -> List[str]:
        """Build codex CLI command."""
        return ["codex", "exec", "--full-auto", prompt]

    def get_output_instruction(self, output_type: str) -> str:
        """Return format instruction for Codex."""
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
            "Codex CLI should be installed and configured.\n"
            "The --full-auto flag enables fully autonomous operation."
        )


# Register the provider
LLMProviderRegistry.register(CodexProvider())
