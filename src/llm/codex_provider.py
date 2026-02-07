"""Codex CLI provider implementation."""

from pathlib import Path
from typing import List, Tuple, Optional
from .base_provider import BaseLLMProvider, LLMProviderRegistry


class CodexProvider(BaseLLMProvider):
    """
    Codex CLI provider using `codex exec --full-auto --skip-git-repo-check`.
    """

    OUTPUT_FILENAME = ".codex_last_message.txt"
    MODELS = [
        ("gpt-5.3-codex", "GPT-5.3 Codex"),
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

    @property
    def uses_stdin(self) -> bool:
        """Send prompts via stdin to avoid Windows shell/newline argument issues."""
        return True

    def build_command(self, prompt: str, model: Optional[str] = None,
                      working_directory: Optional[str] = None) -> List[str]:
        """Build codex CLI command.

        The prompt is provided through stdin by LLMWorker.
        """
        cmd = ["codex", "exec", "--skip-git-repo-check", "--full-auto"]
        output_path = self.get_output_last_message_path(working_directory)
        if output_path:
            cmd.extend(["--output-last-message", output_path])
        if model:
            cmd.extend(["--model", model])
        # Use "-" so codex reads initial instructions from stdin.
        cmd.append("-")
        return cmd

    def get_stdin_prompt(self, prompt: str) -> str:
        """Return the prompt to send via stdin."""
        return prompt

    def get_output_instruction(self, output_type: str) -> str:
        """Return format instruction for Codex using centralized standards."""
        return self.get_standard_output_instructions().get(output_type, "")

    def get_output_last_message_path(self, working_directory: Optional[str]) -> Optional[str]:
        if not working_directory:
            return None
        return str(Path(working_directory) / self.OUTPUT_FILENAME)

    def get_setup_instructions(self) -> str:
        return (
            "Codex CLI should be installed and configured.\n"
            "The --full-auto flag enables fully autonomous operation.\n"
            "The --skip-git-repo-check flag avoids CLI errors outside Git repos."
        )


# Register the provider
LLMProviderRegistry.register(CodexProvider())
