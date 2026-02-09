"""Worker for LLM-based error fixing."""

from pathlib import Path
from .base_worker import BaseWorker
from .llm_worker import LLMWorker
from ..core.error_context import ErrorInfo
from ..core.file_manager import FileManager
from ..llm.base_provider import LLMProviderRegistry
from ..llm.prompt_templates import PromptTemplates


class ErrorFixWorker(BaseWorker):
    """Worker that sends error information to an LLM for automated fixing."""

    def __init__(self, error_info: ErrorInfo, provider_name: str, model: str = None):
        super().__init__()
        self.error_info = error_info
        self.provider_name = provider_name
        self.model = model

    def execute(self):
        """Send error to LLM for analysis and fixing."""
        self.log(f"Sending error to {self.provider_name} for analysis...", "info")

        # Clear/create error-conclusion.md before LLM runs
        file_manager = FileManager(self.error_info.working_directory)
        file_manager.clear_error_conclusion()
        self.log("Cleared error-conclusion.md for LLM output", "debug")

        provider = LLMProviderRegistry.get(self.provider_name)

        prompt = PromptTemplates.format_error_fix_prompt(
            phase=self.error_info.phase.name,
            error_summary=self.error_info.error_summary,
            full_error=self.error_info.full_traceback,
            recent_logs="\n".join(self.error_info.recent_logs),
            working_directory=self.error_info.working_directory
        )

        llm_worker = LLMWorker(
            provider=provider,
            prompt=prompt,
            working_directory=self.error_info.working_directory,
            model=self.model,
            debug_stage="error_fix"
        )

        # Forward LLM output to our signals
        llm_worker.signals.llm_output.connect(
            lambda line: self.signals.llm_output.emit(f"[ErrorFix] {line}")
        )

        llm_worker.run()

        self.log("LLM error fix attempt completed", "success")

        # Read the error-conclusion.md to check if LLM succeeded
        conclusion = file_manager.read_error_conclusion()
        if not conclusion or conclusion.strip() == "":
            self.log("error-conclusion.md is empty - LLM may have failed", "warning")
            return {
                "fixed": False,
                "conclusion": "",
                "provider_name": self.provider_name,
                "message": "LLM did not write to error-conclusion.md"
            }

        self.log("LLM wrote conclusion to error-conclusion.md", "success")
        return {
            "fixed": True,
            "conclusion": conclusion,
            "provider_name": self.provider_name,
            "message": "LLM attempted to fix the error"
        }
