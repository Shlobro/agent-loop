"""Worker for Phase 3: Main Execution Loop."""

from .base_worker import BaseWorker
from .llm_worker import LLMWorker
from ..llm.base_provider import LLMProviderRegistry
from ..llm.prompt_templates import PromptTemplates
from ..core.file_manager import FileManager
from ..utils.markdown_parser import has_incomplete_tasks, count_tasks


class ExecutionWorker(BaseWorker):
    """
    Phase 3 worker: Execute a SINGLE task.
    Runs one iteration and returns - orchestration loop is in main_window.
    """

    def __init__(self, provider_name: str = "claude",
                 working_directory: str = None,
                 current_iteration: int = 0,
                 model: str = None):
        super().__init__()
        self.provider_name = provider_name
        self.working_directory = working_directory
        self.current_iteration = current_iteration
        self.model = model

    def execute(self):
        """Execute a single task."""
        self.update_status("Executing single task...")
        self.log(f"=== SINGLE TASK EXECUTION START ===", "phase")
        self.log(f"Working directory: {self.working_directory}", "info")
        self.log(f"Current iteration: {self.current_iteration}", "info")

        provider = LLMProviderRegistry.get(self.provider_name)
        self.log(f"Using LLM provider: {provider.display_name}", "info")

        file_manager = FileManager(self.working_directory)
        file_manager.ensure_files_exist()
        self.log(f"Initialized file manager, tracking files ready", "debug")

        # Check for stop/pause
        if self.should_stop():
            if self._is_paused:
                self.log("Execution paused", "warning")
            else:
                self.log("Execution stopped by user", "warning")
            return {
                "task_completed": False,
                "all_tasks_done": False,
                "iteration": self.current_iteration,
                "stopped_early": True
            }

        # Check if tasks remain
        tasks_content = file_manager.read_tasks()
        if not has_incomplete_tasks(tasks_content):
            self.log("All tasks completed!", "success")
            self.log(f"Final task file content:\n{tasks_content[:500]}{'...' if len(tasks_content) > 500 else ''}", "debug")
            return {
                "task_completed": False,
                "all_tasks_done": True,
                "iteration": self.current_iteration,
                "stopped_early": False
            }

        iteration = self.current_iteration + 1
        self.current_iteration = iteration
        self.update_progress(iteration, iteration)  # Progress is now per-task

        completed, total = count_tasks(tasks_content)
        self.log(f"Iteration {iteration} - Tasks: {completed}/{total} completed", "phase")

        # Log current task state
        task_preview = ""
        incomplete_tasks = [line.strip() for line in tasks_content.split('\n')
                           if line.strip().startswith('- [ ]')]
        if incomplete_tasks:
            task_preview = incomplete_tasks[0][6:].strip()
            if len(task_preview) > 80:
                task_preview = f"{task_preview[:77]}..."
            self.update_status(f"Task {iteration}: {task_preview}")
            self.log(f"Working on task: {incomplete_tasks[0][:100]}", "info")
            self.log(f"Remaining incomplete tasks: {len(incomplete_tasks)}", "debug")

        # Build the execution prompt
        recent_changes = file_manager.read_recent_changes()
        self.log(f"Read recent-changes.md ({len(recent_changes)} chars)", "debug")

        compliance_report = file_manager.get_workspace_rule_report(use_cache=False)
        if compliance_report.startswith("Workspace compliance scan failed:"):
            self.log(compliance_report, "warning")
        elif compliance_report == "No compliance issues detected.":
            self.log("Workspace compliance check passed", "debug")
        else:
            self.log("Workspace compliance issues detected", "warning")
            self.log(compliance_report, "debug")

        prompt = PromptTemplates.format_execution_prompt(
            working_directory=self.working_directory,
            recent_changes=recent_changes,
            tasks=tasks_content,
            compliance_report=compliance_report
        )
        self.log(f"Built execution prompt ({len(prompt)} chars)", "debug")

        # Run LLM
        if task_preview:
            self.update_status(f"Executing: {task_preview}")
        else:
            self.update_status(f"Executing task (iteration {iteration})...")
        self.log(f"Invoking LLM for task execution...", "info")

        llm_worker = LLMWorker(
            provider=provider,
            prompt=prompt,
            working_directory=self.working_directory,
            timeout=600,  # 10 minutes for execution tasks
            model=self.model,
            debug_stage="execution"
        )

        # Forward signals
        llm_worker.signals.llm_output.connect(
            lambda line: self.signals.llm_output.emit(line)
        )

        llm_worker.run()

        if llm_worker._is_cancelled:
            self.log("LLM worker was cancelled", "warning")
            self.check_cancelled()

        # Signal iteration complete
        self.signals.iteration_complete.emit(iteration)
        self.log(f"Iteration {iteration} LLM execution complete", "debug")

        # Re-read tasks to check progress
        new_tasks_content = file_manager.read_tasks()
        new_completed, new_total = count_tasks(new_tasks_content)

        task_was_completed = False
        if new_completed > completed:
            task_diff = new_completed - completed
            task_was_completed = True
            self.log(f"Completed {task_diff} task(s) this iteration", "success")
            # Log which tasks were completed
            old_incomplete = set(line.strip() for line in tasks_content.split('\n')
                                if line.strip().startswith('- [ ]'))
            new_incomplete = set(line.strip() for line in new_tasks_content.split('\n')
                                if line.strip().startswith('- [ ]'))
            completed_tasks = old_incomplete - new_incomplete
            for task in completed_tasks:
                self.log(f"  [x] {task[6:][:80]}{'...' if len(task) > 86 else ''}", "success")
            self.signals.task_completed.emit(f"Iteration {iteration}: {task_diff} task(s) completed")
        else:
            self.log("No tasks marked complete this iteration", "warning")
            self.log("LLM may have made partial progress or encountered issues", "debug")

        # Log any new tasks that were added
        if new_total > total:
            self.log(f"LLM added {new_total - total} new task(s) to the list", "info")

        # Check if all tasks are now done
        all_done = not has_incomplete_tasks(new_tasks_content)

        self.log(f"=== SINGLE TASK EXECUTION END ===", "phase")

        return {
            "task_completed": task_was_completed,
            "all_tasks_done": all_done,
            "iteration": self.current_iteration,
            "stopped_early": self._is_cancelled or self._is_paused
        }
