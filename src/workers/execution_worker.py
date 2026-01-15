"""Worker for Phase 3: Main Execution Loop."""

from .base_worker import BaseWorker
from .llm_worker import LLMWorker
from ..llm.base_provider import LLMProviderRegistry
from ..llm.prompt_templates import PromptTemplates
from ..core.file_manager import FileManager
from ..utils.markdown_parser import has_incomplete_tasks, count_tasks


class ExecutionWorker(BaseWorker):
    """
    Phase 3 worker: Main execution loop.
    Continues until tasks.md is empty, max iterations reached, or stopped.
    """

    def __init__(self, provider_name: str = "claude",
                 working_directory: str = None,
                 max_iterations: int = 50,
                 start_iteration: int = 0):
        super().__init__()
        self.provider_name = provider_name
        self.working_directory = working_directory
        self.max_iterations = max_iterations
        self.start_iteration = start_iteration
        self.current_iteration = start_iteration

    def execute(self):
        """Run the main execution loop."""
        self.update_status("Starting main execution loop...")

        provider = LLMProviderRegistry.get(self.provider_name)
        file_manager = FileManager(self.working_directory)
        file_manager.ensure_files_exist()

        iteration = self.start_iteration

        while iteration < self.max_iterations:
            # Check for stop/pause
            if self.should_stop():
                if self._is_paused:
                    self.log("Execution paused", "warning")
                    self.wait_if_paused()
                else:
                    self.log("Execution stopped by user", "warning")
                    break

            # Check if tasks remain
            tasks_content = file_manager.read_tasks()
            if not has_incomplete_tasks(tasks_content):
                self.log("All tasks completed!", "success")
                break

            iteration += 1
            self.current_iteration = iteration
            self.update_progress(iteration, self.max_iterations)

            completed, total = count_tasks(tasks_content)
            self.log(f"Iteration {iteration}/{self.max_iterations} - Tasks: {completed}/{total} completed", "phase")

            # Build the execution prompt
            recent_changes = file_manager.read_recent_changes()
            prompt = PromptTemplates.format_execution_prompt(
                working_directory=self.working_directory,
                recent_changes=recent_changes,
                tasks=tasks_content
            )

            # Run LLM
            self.update_status(f"Executing task (iteration {iteration})...")

            llm_worker = LLMWorker(
                provider=provider,
                prompt=prompt,
                working_directory=self.working_directory,
                timeout=600  # 10 minutes for execution tasks
            )

            # Forward signals
            llm_worker.signals.llm_output.connect(
                lambda line: self.signals.llm_output.emit(line)
            )

            llm_worker.run()

            if llm_worker._is_cancelled:
                self.check_cancelled()

            # Signal iteration complete
            self.signals.iteration_complete.emit(iteration)

            # Re-read tasks to check progress
            new_tasks_content = file_manager.read_tasks()
            new_completed, _ = count_tasks(new_tasks_content)

            if new_completed > completed:
                task_diff = new_completed - completed
                self.log(f"Completed {task_diff} task(s) this iteration", "success")
                self.signals.task_completed.emit(f"Iteration {iteration}: {task_diff} task(s) completed")
            else:
                self.log("No tasks marked complete this iteration", "warning")

        return {
            "iterations_completed": iteration,
            "final_iteration": self.current_iteration,
            "stopped_early": self._is_cancelled or self._is_paused
        }
