"""Claude CLI provider implementation."""

from typing import List, Tuple, Optional
from .base_provider import BaseLLMProvider, LLMProviderRegistry


class ClaudeProvider(BaseLLMProvider):
    """
    Claude CLI provider using `claude -p` command.

    Requires running `claude --dangerously-skip-permissions` once before use.
    """

    MODELS = [
        ("claude-opus-4-6", "Claude Opus 4.6"),
        ("claude-sonnet-4-6", "Claude Sonnet 4.6"),
        ("claude-sonnet-4-5-20250929", "Claude Sonnet 4.5"),
        ("claude-haiku-4-5-20251001", "Claude Haiku 4.5"),
        ("claude-opus-4-1-20250805", "Claude Opus 4.1"),
    ]

    @property
    def name(self) -> str:
        return "claude"

    @property
    def display_name(self) -> str:
        return "Claude"

    def get_models(self) -> List[Tuple[str, str]]:
        """Return available Claude models."""
        return self.MODELS

    @property
    def uses_stdin(self) -> bool:
        """Send prompts via stdin to avoid Windows shell/newline argument issues."""
        return True

    def build_command(self, prompt: str, model: Optional[str] = None,
                      working_directory: Optional[str] = None) -> List[str]:
        """Build claude CLI command with auto-approval.

        The prompt is provided through stdin by LLMWorker.
        """
        cmd = ["claude", "--dangerously-skip-permissions"]
        if model:
            cmd.extend(["--model", model])
        cmd.append("-p")
        return cmd

    def get_stdin_prompt(self, prompt: str) -> str:
        """Return the prompt to send via stdin."""
        return prompt

    def get_output_instruction(self, output_type: str) -> str:
        """Return format instruction for Claude using centralized standards."""
        return self.get_standard_output_instructions().get(output_type, "")

    def get_setup_instructions(self) -> str:
        return (
            "Before using Claude, run this command once:\n"
            "  claude --dangerously-skip-permissions\n\n"
            "This allows Claude to run in non-interactive mode."
        )


# Register the provider
LLMProviderRegistry.register(ClaudeProvider())
