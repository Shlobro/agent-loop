"""Worker for Phase 2: Task Planning."""

from typing import Dict

from .base_worker import BaseWorker
from .llm_worker import LLMWorker
from ..llm.base_provider import LLMProviderRegistry
from ..llm.prompt_templates import PromptTemplates
from ..core.file_manager import FileManager
from ..utils.markdown_parser import parse_tasks


class PlanningWorker(BaseWorker):
    """
    Phase 2 worker: Generates task list from description and answers.
    """

    def __init__(self, description: str, answers: Dict[str, str],
                 provider_name: str = "claude",
                 working_directory: str = None):
        super().__init__()
        self.description = description
        self.answers = answers
        self.provider_name = provider_name
        self.working_directory = working_directory

    def execute(self):
        """Generate task list and save to tasks.md."""
        self.update_status("Creating task list...")

        provider = LLMProviderRegistry.get(self.provider_name)

        # Build prompt
        base_prompt = PromptTemplates.format_planning_prompt(
            self.description,
            self.answers
        )
        prompt = provider.format_prompt(base_prompt, "markdown_tasks")

        # Run LLM
        self.log(f"Calling {provider.display_name} for task planning...", "info")

        llm_worker = LLMWorker(
            provider=provider,
            prompt=prompt,
            working_directory=self.working_directory
        )

        # Forward LLM output signals
        llm_worker.signals.llm_output.connect(
            lambda line: self.signals.llm_output.emit(line)
        )

        llm_worker.run()

        if llm_worker._is_cancelled:
            self.check_cancelled()

        output = ''.join(llm_worker._output_lines)

        # Validate that we got tasks
        tasks = parse_tasks(output)
        if not tasks:
            # Try to extract just the task lines from the output
            lines = output.split('\n')
            task_lines = [line for line in lines if line.strip().startswith('- [')]
            if task_lines:
                output = '\n'.join(task_lines)
                tasks = parse_tasks(output)

        if not tasks:
            self.log("Warning: No tasks found in LLM output", "warning")
        else:
            self.log(f"Created {len(tasks)} tasks", "success")

        # Ensure we have a proper header
        if not output.strip().startswith('#'):
            output = f"# Tasks\n\n{output}"

        # Save to file
        if self.working_directory:
            file_manager = FileManager(self.working_directory)
            file_manager.ensure_files_exist()
            file_manager.write_tasks(output)
            self.log(f"Saved tasks to {file_manager.tasks_file}", "info")

        self.signals.tasks_ready.emit(output)
        return {
            "tasks_content": output,
            "task_count": len(tasks)
        }
