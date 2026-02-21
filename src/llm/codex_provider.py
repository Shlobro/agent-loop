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
        ("gpt-5.3-codex", "GPT-5.3 Codex (Medium)"),
        ("gpt-5.3-codex:low", "GPT-5.3 Codex (Low)"),
        ("gpt-5.3-codex:high", "GPT-5.3 Codex (High)"),
        ("gpt-5.3-codex:xhigh", "GPT-5.3 Codex (Ultra High)"),
        ("gpt-5.2-codex", "GPT-5.2 Codex (Medium)"),
        ("gpt-5.2-codex:low", "GPT-5.2 Codex (Low)"),
        ("gpt-5.2-codex:high", "GPT-5.2 Codex (High)"),
        ("gpt-5.2-codex:xhigh", "GPT-5.2 Codex (Ultra High)"),
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

        normalized_working_directory: Optional[str] = None
        if working_directory and str(working_directory).strip():
            candidate_working_directory = Path(working_directory)
            if candidate_working_directory.exists() and candidate_working_directory.is_dir():
                normalized_working_directory = str(candidate_working_directory)
        if normalized_working_directory:
            # Ensure Codex workspace-write sandbox is rooted at the selected project.
            cmd.extend(["--cd", normalized_working_directory])
            # Explicitly grant write access to the selected project tree.
            cmd.extend(["--add-dir", normalized_working_directory])
        
        # Parse reasoning effort from model ID if present (e.g. "gpt-5.3-codex:high")
        actual_model = model
        reasoning_effort = None
        if model and ":" in model:
            actual_model, reasoning_effort = model.split(":", 1)

        output_path = self.get_output_last_message_path(normalized_working_directory)
        if output_path:
            cmd.extend(["--output-last-message", output_path])
            
        if actual_model:
            cmd.extend(["--model", actual_model])
            
        if reasoning_effort:
            cmd.extend(["-c", f"model_reasoning_effort={reasoning_effort}"])

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
