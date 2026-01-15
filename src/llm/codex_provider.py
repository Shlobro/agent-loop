"""Codex CLI provider implementation."""

from typing import List, Tuple, Optional
from .base_provider import BaseLLMProvider, LLMProviderRegistry


class CodexProvider(BaseLLMProvider):
    """
    Codex CLI provider using `codex exec --full-auto` command.
    """

    MODELS = [
        ("gpt-5.2-codex", "GPT-5.2 Codex"),
        ("gpt-5.1-codex-max", "GPT-5.1 Codex Max"),
        ("gpt-5.1-codex-mini", "GPT-5.1 Codex Mini"),
        ("gpt-5.2", "GPT-5.2"),
    ]

    @property
    def name(self) -> str:
        return "codex"

    @property
    def display_name(self) -> str:
        return "Codex"

    def get_models(self) -> List[Tuple[str, str]]:
        """Return available Codex models."""
        return self.MODELS

    def build_command(self, prompt: str, model: Optional[str] = None) -> List[str]:
        """Build codex CLI command."""
        cmd = ["codex", "exec", "--full-auto"]
        if model:
            cmd.extend(["--model", model])
        cmd.append(prompt)
        return cmd

    def get_output_instruction(self, output_type: str) -> str:
        """Return format instruction for Codex using centralized standards."""
        return self.get_standard_output_instructions().get(output_type, "")

    def get_setup_instructions(self) -> str:
        return (
            "Codex CLI should be installed and configured.\n"
            "The --full-auto flag enables fully autonomous operation."
        )


# Register the provider
LLMProviderRegistry.register(CodexProvider())
