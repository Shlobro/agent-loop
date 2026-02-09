"""Worker for processing chat messages that initialize or update product description."""

from pathlib import Path
from typing import Optional
from .base_worker import BaseWorker
from .llm_worker import LLMWorker
from ..llm.base_provider import LLMProviderRegistry
from ..llm.prompt_templates import PromptTemplates
from ..core.file_manager import FileManager


class ChatToDescriptionWorker(BaseWorker):
    """
    Process chat messages that should directly initialize or update product description.

    Used when:
    - Product description is empty (initialization)
    - Product description exists but needs updating based on chat message

    Returns whether the description was changed.
    """

    def __init__(
        self,
        message: str,
        provider_name: str,
        working_directory: str,
        is_initialization: bool,
        model: Optional[str] = None,
        debug_mode: bool = False,
        debug_breakpoints: dict = None,
        show_terminal: bool = True
    ):
        super().__init__()
        self.message = message
        self.provider_name = provider_name
        self.working_directory = working_directory
        self.is_initialization = is_initialization
        self.model = model
        self.debug_mode = debug_mode
        self.debug_breakpoints = debug_breakpoints or {}
        self.show_terminal = show_terminal
        self.file_manager = FileManager(working_directory)

    def execute(self):
        """Process chat message to initialize or update product description."""
        if self.is_initialization:
            self.update_status("Initializing product description from chat...")
            self.log("Initializing product description from first chat message", "info")
        else:
            self.update_status("Updating product description from chat...")
            self.log("Updating product description based on chat message", "info")

        # Get provider instance
        provider = LLMProviderRegistry.get(self.provider_name)
        self.log(f"Using LLM provider: {provider.display_name}", "info")

        # Read current description to detect changes
        old_description = self.file_manager.read_description()

        # Build prompt based on initialization or update
        if self.is_initialization:
            prompt = PromptTemplates.format_description_initialize_prompt(self.message)
            stage = "description_initialization"
        else:
            prompt = PromptTemplates.format_description_update_prompt(self.message)
            stage = "description_update"

        # Call LLM using LLMWorker
        self.log(f"Calling {provider.display_name} for {stage}", "info")

        llm_worker = LLMWorker(
            provider=provider,
            prompt=prompt,
            working_directory=self.working_directory,
            model=self.model,
            debug_stage=stage
        )

        # Connect LLM worker signals to bubble up
        llm_worker.signals.log.connect(lambda msg, lvl: self.signals.log.emit(msg, lvl))
        llm_worker.signals.llm_output.connect(lambda msg: self.signals.llm_output.emit(msg))

        # Execute LLM call synchronously (we're already in a worker thread)
        llm_result = llm_worker.execute()

        # Read new description to check if it changed
        new_description = self.file_manager.read_description()
        description_changed = new_description != old_description

        if description_changed:
            self.log("Product description updated successfully", "success")
        else:
            self.log("Product description unchanged", "info")

        return {
            "description_changed": description_changed,
            "new_description": new_description,
            "llm_result": llm_result
        }
