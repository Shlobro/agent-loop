"""Gemini CLI provider implementation."""

from typing import List, Tuple, Optional
from .base_provider import BaseLLMProvider, LLMProviderRegistry


class GeminiProvider(BaseLLMProvider):
    """
    Gemini CLI provider using `gemini` command with --yolo flag.

    Uses stdin to pass the prompt to avoid shell escaping issues.
    """

    MODELS = [
        ("gemini-3-pro-preview", "Gemini 3 Pro (Preview)"),
        ("gemini-3-flash-preview", "Gemini 3 Flash (Preview)"),
        ("gemini-2.5-pro", "Gemini 2.5 Pro"),
        ("gemini-2.5-flash", "Gemini 2.5 Flash"),
        ("gemini-2.5-flash-lite", "Gemini 2.5 Flash Lite"),
    ]

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def display_name(self) -> str:
        return "Gemini"

    def get_models(self) -> List[Tuple[str, str]]:
        """Return available Gemini models."""
        return self.MODELS

    @property
    def uses_stdin(self) -> bool:
        """Gemini accepts prompt via stdin to avoid escaping issues."""
        return True

    def build_command(self, prompt: str, model: Optional[str] = None,
                      working_directory: Optional[str] = None) -> List[str]:
        """Build gemini CLI command.

        The prompt will be passed via stdin by the LLMWorker.
        """
        cmd = ["gemini"]
        if model:
            cmd.extend(["--model", model])
        cmd.append("--yolo")
        return cmd

    def get_stdin_prompt(self, prompt: str) -> str:
        """Return the prompt to send via stdin."""
        return prompt

    def get_output_instruction(self, output_type: str) -> str:
        """Return format instruction for Gemini using centralized standards."""
        return self.get_standard_output_instructions().get(output_type, "")

    def get_setup_instructions(self) -> str:
        return (
            "Gemini CLI should be installed and configured with API credentials.\n"
            "The --yolo flag enables autonomous operation."
        )


# Register the provider
LLMProviderRegistry.register(GeminiProvider())
