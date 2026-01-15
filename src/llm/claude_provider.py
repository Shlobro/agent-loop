"""Claude CLI provider implementation."""

from typing import List
from .base_provider import BaseLLMProvider, LLMProviderRegistry


class ClaudeProvider(BaseLLMProvider):
    """
    Claude CLI provider using `claude -p` command.

    Requires running `claude --dangerously-skip-permissions` once before use.
    """

    @property
    def name(self) -> str:
        return "claude"

    @property
    def display_name(self) -> str:
        return "Claude"

    def build_command(self, prompt: str) -> List[str]:
        """Build claude CLI command."""
        return ["claude", "-p", prompt]

    def get_output_instruction(self, output_type: str) -> str:
        """Return format instruction for Claude."""
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
            "Before using Claude, run this command once:\n"
            "  claude --dangerously-skip-permissions\n\n"
            "This allows Claude to run in non-interactive mode."
        )


# Register the provider
LLMProviderRegistry.register(ClaudeProvider())
