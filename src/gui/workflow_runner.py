"""Workflow execution helpers for MainWindow."""

from PySide6.QtCore import Slot

from ..core.state_machine import Phase
from ..llm.prompt_templates import PromptTemplates
from ..workers.planning_worker import PlanningWorker
from ..workers.execution_worker import ExecutionWorker
from ..workers.review_worker import ReviewWorker
from ..workers.git_worker import GitWorker


class WorkflowRunnerMixin:
    """Shared worker execution logic for MainWindow."""

    def run_task_planning(self):
        """Run Phase 2: Task Planning."""
        ctx = self.state_machine.context

        worker = PlanningWorker(
            description=ctx.description,
            answers=ctx.answers,
            qa_pairs=ctx.qa_pairs,
            provider_name=ctx.llm_config.get("task_planning", "claude"),
            working_directory=ctx.working_directory,
            model=ctx.llm_config.get("task_planning_model")
        )

        self._connect_worker_signals(worker)
        worker.signals.tasks_ready.connect(self.on_tasks_ready)

        self.current_worker = worker
        self.thread_pool.start(worker)

    @Slot(str)
    def on_tasks_ready(self, tasks_content: str):
        """Handle generated tasks."""
        self.state_machine.update_context(tasks_content=tasks_content)
        self.log_viewer.append_success("Task list created")
        self._refresh_task_loop_snapshot(action="Task list created")

        # Move to main execution
        self.log_viewer.append_log("Transitioning to Main Execution phase...", "info")
        self.state_machine.transition_to(Phase.MAIN_EXECUTION)
        self.run_main_execution()

    def run_main_execution(self):
        """Run Phase 3: Execute a single task."""
        ctx = self.state_machine.context

        # Check max iterations limit
        if ctx.current_iteration >= ctx.max_iterations:
            self.log_viewer.append_log(f"Max iterations ({ctx.max_iterations}) reached", "warning")

            # Check if there are still incomplete tasks
            from ..utils.markdown_parser import has_incomplete_tasks
            if self.file_manager:
                tasks_content = self.file_manager.read_tasks()
                if has_incomplete_tasks(tasks_content):
                    self._prompt_continue_iterations()
                    return

            self.state_machine.transition_to(Phase.COMPLETED)
            return

        worker = ExecutionWorker(
            provider_name=ctx.llm_config.get("coder", "claude"),
            working_directory=ctx.working_directory,
            current_iteration=ctx.current_iteration,
            model=ctx.llm_config.get("coder_model"),
            tasks_per_iteration=ctx.tasks_per_iteration
        )

        self._connect_worker_signals(worker)
        worker.signals.iteration_complete.connect(self.on_iteration_complete)
        worker.signals.result.connect(self.on_single_task_complete)

        self.current_worker = worker
        self.thread_pool.start(worker)

    @Slot(int)
    def on_iteration_complete(self, iteration: int):
        """Handle iteration completion."""
        ctx = self.state_machine.context
        self.state_machine.update_context(current_iteration=iteration)
        self.status_panel.set_iteration(iteration, ctx.max_iterations)
        self._refresh_task_loop_snapshot(action=f"Iteration {iteration} completed")

    @Slot(object)
    def on_single_task_complete(self, result: dict):
        """Handle single task execution completion - then proceed to review and git."""
        self.log_viewer.append_log(f"Single task execution result: {result}", "debug")
        self._refresh_task_loop_snapshot(action=f"Main loop iteration {result.get('iteration', 0)} finished")

        if result.get("stopped_early"):
            self.log_viewer.append_log("Execution stopped early", "warning")
            if self.state_machine.context.pause_requested:
                self.state_machine.transition_to(Phase.PAUSED)
            return

        # Update iteration count
        self.state_machine.update_context(current_iteration=result.get("iteration", 0))

        # Check if all tasks are done
        if result.get("all_tasks_done"):
            self.log_viewer.append_log("All tasks completed!", "success")

            self._run_review_or_git(is_final=True)
            return

        # Task was worked on - now run review loop for this task's changes
        self.log_viewer.append_log(f"Task iteration {result.get('iteration')} complete", "success")

        # Check if we should run review loop
        self._run_review_or_git(is_final=False)

    def run_review_loop(self):
        """Run Phase 4: Debug/Review Loop."""
        ctx = self.state_machine.context
        if not ctx.review_types:
            self.log_viewer.append_log("No review types selected - skipping review loop", "warning")
            self.state_machine.transition_to(Phase.GIT_OPERATIONS)
            self.run_git_operations()
            return

        worker = ReviewWorker(
            reviewer_provider_name=ctx.llm_config.get("reviewer", "claude"),
            fixer_provider_name=ctx.llm_config.get("fixer", "claude"),
            working_directory=ctx.working_directory,
            iterations=ctx.debug_iterations,
            start_iteration=ctx.current_debug_iteration,
            review_types=ctx.review_types,
            run_unit_test_prep=ctx.run_unit_test_prep,
            reviewer_model=ctx.llm_config.get("reviewer_model"),
            fixer_model=ctx.llm_config.get("fixer_model"),
            unit_test_prep_provider_name=ctx.llm_config.get("unit_test_prep", "gemini"),
            unit_test_prep_model=ctx.llm_config.get("unit_test_prep_model", "gemini-3-pro-preview"),
            runtime_config_provider=lambda: {
                "debug_iterations": self.state_machine.context.debug_iterations,
                "reviewer": self.state_machine.context.llm_config.get("reviewer", "claude"),
                "fixer": self.state_machine.context.llm_config.get("fixer", "claude"),
                "reviewer_model": self.state_machine.context.llm_config.get("reviewer_model"),
                "fixer_model": self.state_machine.context.llm_config.get("fixer_model"),
                "unit_test_prep": self.state_machine.context.llm_config.get("unit_test_prep", "gemini"),
                "unit_test_prep_model": self.state_machine.context.llm_config.get("unit_test_prep_model", "gemini-3-pro-preview"),
            }
        )

        self._connect_worker_signals(worker)
        worker.signals.review_complete.connect(self.on_review_complete)
        worker.signals.result.connect(self.on_review_loop_complete)

        self.current_worker = worker
        self.thread_pool.start(worker)

    @Slot(str, str)
    def on_review_complete(self, review_type: str, result: str):
        """Handle individual review completion."""
        self.state_machine.update_context(current_review_type=review_type)
        review_label = PromptTemplates.get_review_display_name(review_type)
        self.status_panel.set_sub_status(f"Completed: {review_label}")
        self._refresh_task_loop_snapshot(action=f"Completed review: {review_label}")

        if self._should_show_activity(self.state_machine.phase):
            self.activity_state["review"] = review_label
            self.activity_state["action"] = f"Completed: {review_label}"
            self._refresh_activity_panel()

    @Slot(object)
    def on_review_loop_complete(self, result: dict):
        """Handle review loop completion for current task."""
        self.log_viewer.append_log(f"Review loop result: {result}", "debug")

        if result.get("stopped_early"):
            self.log_viewer.append_log("Review loop stopped early", "warning")
            if self.state_machine.context.pause_requested:
                self.state_machine.transition_to(Phase.PAUSED)
            return

        self.log_viewer.append_log(f"Review loop completed: {result.get('review_iterations_completed', 0)} iterations", "success")

        # Move to git operations for this task
        self.log_viewer.append_log("Transitioning to Git Operations for this task...", "info")
        self.state_machine.transition_to(Phase.GIT_OPERATIONS)
        self.run_git_operations()

    def run_git_operations(self):
        """Run Phase 5: Git Operations."""
        ctx = self.state_machine.context
        git_mode = ctx.git_mode
        if git_mode == "off":
            self.log_viewer.append_log("Git mode is Off - skipping git operations", "info")
            self.on_git_complete({"committed": False, "pushed": False, "skipped": True})
            return

        push_enabled = git_mode == "push"
        self.log_viewer.append_log(f"Git mode: {git_mode}", "info")

        worker = GitWorker(
            provider_name=ctx.llm_config.get("git_ops", "claude"),
            working_directory=ctx.working_directory,
            push_enabled=push_enabled,
            git_remote=ctx.git_remote,
            model=ctx.llm_config.get("git_ops_model")
        )

        self._connect_worker_signals(worker)
        worker.signals.result.connect(self.on_git_complete)

        self.current_worker = worker
        self.thread_pool.start(worker)

    @Slot(object)
    def on_git_complete(self, result: dict):
        """Handle git operations completion - then check for more tasks."""
        self.log_viewer.append_log(f"Git operations result: {result}", "debug")
        self._refresh_task_loop_snapshot(action="Git operations finished")

        if result.get("skipped"):
            self.log_viewer.append_log("Git operations skipped (no changes detected)", "info")
        elif result.get("committed"):
            self.log_viewer.append_success("Changes committed to local repository")
        else:
            self.log_viewer.append_warning("No commit was made")

        if result.get("pushed"):
            self.log_viewer.append_success("Changes pushed to remote repository")
        elif not result.get("skipped"):
            self.log_viewer.append_log("Changes were NOT pushed to remote", "info")

        # Clear recent-changes.md for the next task (so reviews are scoped to that task's changes)
        self._clear_recent_changes()

        # Check if there are more incomplete tasks
        from ..utils.markdown_parser import has_incomplete_tasks
        ctx = self.state_machine.context

        if self.file_manager:
            tasks_content = self.file_manager.read_tasks()
            if has_incomplete_tasks(tasks_content):
                # More tasks remain - cycle back to main execution
                self.log_viewer.append_log("=" * 50, "info")
                self.log_viewer.append_log("More tasks remaining - starting next task...", "info")
                self.log_viewer.append_log("=" * 50, "info")
                self.state_machine.transition_to(Phase.MAIN_EXECUTION)
                self.run_main_execution()
                return

        # All tasks done - workflow complete
        self.log_viewer.append_log("All tasks have been completed!", "success")

        # Clean up session file
        try:
            self.session_manager.delete_session()
            self.log_viewer.append_log("Session file cleaned up", "debug")
        except Exception as e:
            self.log_viewer.append_log(f"Failed to delete session: {e}", "debug")

        self.log_viewer.append_log("Transitioning to Completed phase...", "info")
        self.state_machine.transition_to(Phase.COMPLETED)

    def _clear_recent_changes(self):
        """Clear recent-changes.md after git push so next task starts fresh."""
        if self.file_manager:
            try:
                self.file_manager.write_recent_changes("# Recent Changes\n\n")
                self.log_viewer.append_log("Cleared recent-changes.md for next task", "debug")
            except Exception as e:
                self.log_viewer.append_log(f"Failed to clear recent-changes.md: {e}", "warning")

    def _should_run_review_loop(self) -> bool:
        """Return True if review loop is configured to run."""
        ctx = self.state_machine.context
        return ctx.debug_iterations > 0 and bool(ctx.review_types)

    def _run_review_or_git(self, is_final: bool):
        """Route to review loop or git operations for the current task."""
        ctx = self.state_machine.context
        scope_label = "final " if is_final else ""
        git_scope_label = "final changes" if is_final else "this task"

        if self._should_run_review_loop():
            self.log_viewer.append_log(
                f"Running {scope_label}Debug/Review ({ctx.debug_iterations} iterations)...",
                "info"
            )
            self.state_machine.transition_to(Phase.DEBUG_REVIEW)
            self.run_review_loop()
            return

        if ctx.debug_iterations == 0:
            reason = "0 iterations configured"
        else:
            reason = "no review types selected"
        self.log_viewer.append_log(f"Skipping {scope_label}Debug/Review phase ({reason})", "info")
        self.log_viewer.append_log(f"Transitioning to Git Operations for {git_scope_label}...", "info")
        self.state_machine.transition_to(Phase.GIT_OPERATIONS)
        self.run_git_operations()

    def _connect_worker_signals(self, worker):
        """Connect common worker signals."""
        worker.signals.log.connect(self.log_viewer.append_log)
        worker.signals.llm_output.connect(self.log_viewer.append_llm_output)
        worker.signals.status.connect(self.on_worker_status)
        worker.signals.review_summary.connect(self.on_review_summary)
        worker.signals.error.connect(self.on_worker_error)
        worker.signals.finished.connect(self.on_worker_finished)

    @Slot(tuple)
    def on_worker_error(self, error_info):
        """Handle worker error."""
        exc_type, exc_value, tb_str = error_info
        self.log_viewer.append_error(f"Error: {exc_value}")
        self.log_viewer.append_log(f"Exception type: {exc_type.__name__ if exc_type else 'Unknown'}", "debug")
        if tb_str:
            # Log first few lines of traceback
            tb_lines = tb_str.strip().split('\n')
            for line in tb_lines[-5:]:  # Last 5 lines
                self.log_viewer.append_log(f"  {line}", "debug")
        self.state_machine.set_error(str(exc_value))

    @Slot()
    def on_worker_finished(self):
        """Handle worker completion."""
        self.current_worker = None
        self._set_debug_waiting(False)
        self.update_button_states()
