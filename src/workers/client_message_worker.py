"""Worker for processing client messages with LLM."""

from pathlib import Path
from typing import Optional
from .base_worker import BaseWorker
from .llm_worker import LLMWorker
from ..llm.base_provider import LLMProviderRegistry
from ..llm.prompt_templates import PromptTemplates
from ..core.file_manager import FileManager


class ClientMessageWorker(BaseWorker):
    """
    Process client messages sent during workflow execution.

    Uses LLM to decide whether to update product-description.md/tasks.md
    or provide an answer in answer.md.
    """

    def __init__(
        self,
        message: str,
        provider_name: str,
        working_directory: str,
        model: Optional[str] = None,
        debug_mode: bool = False,
        debug_breakpoints: dict = None,
        show_terminal: bool = True,
        update_description: bool = None,
        add_tasks: bool = None,
        provide_answer: bool = None
    ):
        super().__init__()
        self.message = message
        self.provider_name = provider_name
        self.working_directory = working_directory
        self.model = model
        self.debug_mode = debug_mode
        self.debug_breakpoints = debug_breakpoints or {}
        self.show_terminal = show_terminal
        self.update_description = update_description
        self.add_tasks = add_tasks
        self.provide_answer = provide_answer
        self.file_manager = FileManager(working_directory)

    def execute(self):
        """Process client message with LLM."""
        self.update_status("Processing client message...")

        # Get provider instance
        provider = LLMProviderRegistry.get(self.provider_name)
        self.log(f"Using LLM provider: {provider.display_name}", "info")

        # Truncate answer.md before LLM call
        self.log("Truncating answer.md", "debug")
        self.file_manager.truncate_answer()

        # Build prompt with checkbox states
        prompt = PromptTemplates.format_client_message_prompt(
            self.message,
            update_description=self.update_description,
            add_tasks=self.add_tasks,
            provide_answer=self.provide_answer
        )

        # Call LLM using LLMWorker
        self.log(f"Calling {provider.display_name} for client message handling", "info")

        llm_worker = LLMWorker(
            provider=provider,
            prompt=prompt,
            working_directory=self.working_directory,
            model=self.model,
            debug_stage="client_message_handler"
        )

        # Connect LLM worker signals to bubble up
        llm_worker.signals.log.connect(lambda msg, lvl: self.signals.log.emit(msg, lvl))
        llm_worker.signals.llm_output.connect(lambda msg: self.signals.llm_output.emit(msg))

        # Execute LLM call synchronously (we're already in a worker thread)
        llm_result = llm_worker.execute()

        # Read answer.md to check if answer was provided
        answer_content = self.file_manager.read_answer()
        has_answer = len(answer_content.strip()) > 0

        return {
            "has_answer": has_answer,
            "answer_content": answer_content if has_answer else "",
            "llm_result": llm_result
        }
