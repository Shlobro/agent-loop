"""Abstract base class for LLM CLI providers."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseLLMProvider(ABC):
    """Abstract base class for LLM CLI providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return provider name (e.g., 'claude', 'gemini', 'codex')."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Return human-readable provider name."""
        pass

    @abstractmethod
    def build_command(self, prompt: str) -> List[str]:
        """
        Build the CLI command for invoking the LLM.

        Args:
            prompt: The prompt to send to the LLM

        Returns:
            List suitable for subprocess.Popen()
        """
        pass

    @abstractmethod
    def get_output_instruction(self, output_type: str) -> str:
        """
        Return instruction string for enforcing output format.

        Args:
            output_type: One of 'json', 'markdown_tasks', 'review', 'freeform'

        Returns:
            Instruction string to append to prompts
        """
        pass

    def format_prompt(self, base_prompt: str, output_type: str = "freeform") -> str:
        """
        Format a prompt with output instructions.

        Args:
            base_prompt: The main prompt content
            output_type: The expected output format

        Returns:
            Complete prompt with format instructions
        """
        instruction = self.get_output_instruction(output_type)
        if instruction:
            return f"{base_prompt}\n\n{instruction}"
        return base_prompt

    @property
    def uses_stdin(self) -> bool:
        """
        Whether this provider receives prompt via stdin instead of command args.
        Override in subclasses that use stdin.
        """
        return False

    def get_stdin_prompt(self, prompt: str) -> str:
        """
        Return the prompt to send via stdin.
        Only used if uses_stdin is True.
        """
        return prompt

    def get_setup_instructions(self) -> str:
        """
        Return setup instructions for this provider.
        Override in subclasses if special setup is needed.
        """
        return ""

    def validate_installation(self) -> Dict[str, Any]:
        """
        Check if the LLM CLI is properly installed.

        Returns:
            Dict with 'installed' (bool), 'version' (str or None), 'error' (str or None)
        """
        import subprocess
        import shutil

        result = {
            "installed": False,
            "version": None,
            "error": None
        }

        # Check if command exists
        cmd = self.build_command("test")[0]
        if not shutil.which(cmd):
            result["error"] = f"Command '{cmd}' not found in PATH"
            return result

        result["installed"] = True
        return result


class LLMProviderRegistry:
    """Registry for LLM providers."""

    _providers: Dict[str, BaseLLMProvider] = {}

    @classmethod
    def register(cls, provider: BaseLLMProvider):
        """Register a provider instance."""
        cls._providers[provider.name] = provider

    @classmethod
    def get(cls, name: str) -> BaseLLMProvider:
        """Get a provider by name."""
        if name not in cls._providers:
            raise ValueError(f"Unknown LLM provider: {name}")
        return cls._providers[name]

    @classmethod
    def get_all(cls) -> Dict[str, BaseLLMProvider]:
        """Get all registered providers."""
        return cls._providers.copy()

    @classmethod
    def get_names(cls) -> List[str]:
        """Get list of registered provider names."""
        return list(cls._providers.keys())

    @classmethod
    def get_display_names(cls) -> Dict[str, str]:
        """Get mapping of provider names to display names."""
        return {name: p.display_name for name, p in cls._providers.items()}
