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
        """Handle git operations completion - process client messages then check for more tasks."""
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

        # Process pending client messages before continuing
        ctx = self.state_machine.context
        if ctx.pending_client_messages:
            self._process_client_messages()
            return  # Will continue after messages processed

        # Check if there are more incomplete tasks
        from ..utils.markdown_parser import has_incomplete_tasks

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
    def on_worker_error(self, error_info_tuple):
        """Handle worker error by showing recovery dialog."""
        exc_type, exc_value, tb_str = error_info_tuple
        if hasattr(self, "chat_panel"):
            self.chat_panel.clear_bot_activity()

        # Log the error first
        self.log_viewer.append_error(f"Error: {exc_value}")
        self.log_viewer.append_log(f"Exception type: {exc_type.__name__ if exc_type else 'Unknown'}", "debug")

        # Capture full error context
        error_info = self._capture_error_context(exc_type, exc_value, tb_str)

        # Transition to error state
        self.state_machine.set_error(str(exc_value))

        # Show error recovery dialog
        self._show_error_recovery_dialog(error_info)

    @Slot()
    def on_worker_finished(self):
        """Handle worker completion."""
        self.current_worker = None
        self._set_debug_waiting(False)
        self.update_button_states()

    # =========================================================================
    # Error Recovery Methods
    # =========================================================================

    def retry_current_phase(self):
        """Retry the current phase from the beginning."""
        phase = self.state_machine.phase

        retry_methods = {
            Phase.QUESTION_GENERATION: self._retry_question_generation,
            Phase.TASK_PLANNING: self._retry_task_planning,
            Phase.MAIN_EXECUTION: self._retry_main_execution,
            Phase.DEBUG_REVIEW: self._retry_review,
            Phase.GIT_OPERATIONS: self._retry_git_operations,
        }

        retry_method = retry_methods.get(phase)
        if retry_method:
            self.log_viewer.append_log(f"Retrying {phase.name} phase...", "warning")
            self.state_machine.update_context(error_message=None)
            self.state_machine.transition_to(phase)
            retry_method()
        else:
            self.log_viewer.append_warning(f"Cannot retry phase: {phase.name}")

    def _retry_git_operations(self):
        """Retry git operations from step 1 (commit message generation)."""
        from pathlib import Path

        # Clear commit message file
        ctx = self.state_machine.context
        commit_msg_path = Path(ctx.working_directory) / ".agentharness/git-commit-message.txt"
        if commit_msg_path.exists():
            try:
                commit_msg_path.write_text("", encoding="utf-8")
            except Exception as e:
                self.log_viewer.append_log(f"Failed to clear commit message: {e}", "debug")

        self.run_git_operations()  # Existing method

    def _retry_main_execution(self):
        """Retry current task execution without incrementing iteration."""
        self.run_main_execution()

    def _retry_review(self):
        """Retry review loop for current task."""
        self.state_machine.update_context(current_debug_iteration=0)
        self.run_review_loop()

    def _retry_task_planning(self):
        """Retry task planning from scratch."""
        self.run_task_planning()

    def _retry_question_generation(self):
        """Retry question generation from scratch."""
        if self.file_manager:
            try:
                self.file_manager.write_questions({})
            except Exception as e:
                self.log_viewer.append_log(f"Failed to clear questions: {e}", "debug")

        from ..workers.question_worker import QuestionWorker
        ctx = self.state_machine.context

        worker = QuestionWorker(
            description=ctx.description,
            provider_name=ctx.llm_config.get("question_gen", "gemini"),
            working_directory=ctx.working_directory,
            model=ctx.llm_config.get("question_gen_model"),
            question_count=ctx.max_questions
        )

        self._connect_worker_signals(worker)
        worker.signals.questions_ready.connect(self.on_questions_ready)

        self.current_worker = worker
        self.thread_pool.start(worker)

    def skip_to_next_iteration(self):
        """Skip current failed operation and move to next iteration."""
        from PySide6.QtWidgets import QMessageBox

        phase = self.state_machine.phase
        ctx = self.state_machine.context

        self.log_viewer.append_log(f"Skipping {phase.name} phase...", "warning")

        if phase in (Phase.MAIN_EXECUTION, Phase.DEBUG_REVIEW, Phase.GIT_OPERATIONS):
            # These are part of main loop
            self._skip_current_task()
        elif phase == Phase.TASK_PLANNING:
            self.log_viewer.append_warning("Cannot skip planning. Returning to idle.")
            self.state_machine.transition_to(Phase.COMPLETED)
        elif phase == Phase.QUESTION_GENERATION:
            self.log_viewer.append_warning("Skipping questions. Moving to planning.")
            self.state_machine.transition_to(Phase.TASK_PLANNING)
            self.run_task_planning()
        else:
            self.log_viewer.append_warning(f"Cannot skip phase: {phase.name}")
            self.state_machine.transition_to(Phase.COMPLETED)

    def _skip_current_task(self):
        """Skip current task and move to next incomplete task or complete."""
        from PySide6.QtWidgets import QMessageBox
        from ..utils.markdown_parser import has_incomplete_tasks

        ctx = self.state_machine.context

        # Check if this is the last iteration
        if ctx.current_iteration >= ctx.max_iterations:
            reply = QMessageBox.question(
                self, "Last Iteration",
                "This is the last iteration. Skipping will complete the workflow. Continue?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                # Show error recovery dialog again
                return

        # Check for more incomplete tasks
        if self.file_manager:
            tasks_content = self.file_manager.read_tasks()
            if has_incomplete_tasks(tasks_content):
                self.log_viewer.append_log("Moving to next task...", "info")
                self.state_machine.transition_to(Phase.MAIN_EXECUTION)
                self.run_main_execution()
                return

        self.log_viewer.append_log("No more tasks. Completing workflow.", "info")
        self.state_machine.transition_to(Phase.COMPLETED)

    def _capture_error_context(self, exc_type, exc_value, tb_str):
        """Capture complete error context for recovery dialog."""
        import copy
        from ..core.error_context import ErrorInfo

        ctx = self.state_machine.context

        # Extract error summary (first 3 lines or 300 chars)
        error_lines = str(exc_value).split('\n')
        error_summary = '\n'.join(error_lines[:3])
        if len(error_summary) > 300:
            error_summary = error_summary[:297] + "..."

        # Add helpful hints for known errors
        error_str = str(exc_value).lower()
        if "invalid path 'nul'" in error_str:
            error_summary += "\n\nHint: Git on Windows cannot add files named 'nul' (reserved name)."
        elif "timeout" in error_str or "timed out" in error_str:
            error_summary += "\n\nHint: The operation timed out. This may be due to network issues or LLM quota limits."
        elif "quota" in error_str or "rate limit" in error_str:
            error_summary += "\n\nHint: You may have exceeded API rate limits or quota. Consider switching LLM providers."

        # Get recent logs
        recent_logs = self.log_viewer.get_recent_logs(limit=50)

        return ErrorInfo(
            phase=self.state_machine.phase,
            sub_phase=self.state_machine.sub_phase,
            error_summary=error_summary,
            full_traceback=tb_str,
            exception_type=exc_type.__name__ if exc_type else "Unknown",
            exception_value=str(exc_value),
            recent_logs=recent_logs,
            working_directory=ctx.working_directory,
            current_iteration=ctx.current_iteration,
            max_iterations=ctx.max_iterations,
            context_snapshot=copy.deepcopy(ctx)
        )

    def _show_error_recovery_dialog(self, error_info):
        """Show error recovery dialog and handle user choice."""
        from PySide6.QtWidgets import QMessageBox
        from .dialogs.error_recovery_dialog import ErrorRecoveryDialog

        dialog = ErrorRecoveryDialog(self, error_info)
        dialog.retry_requested.connect(lambda: self._handle_error_retry(error_info))
        dialog.skip_requested.connect(lambda: self._handle_error_skip(error_info))
        dialog.send_to_llm_requested.connect(
            lambda provider: self._handle_error_send_to_llm(error_info, provider)
        )
        dialog.exec()

    def _handle_error_retry(self, error_info):
        """Handle retry phase action."""
        from PySide6.QtWidgets import QMessageBox

        phase = error_info.phase
        iteration = error_info.current_iteration

        # Check retry limits
        if not self.error_recovery_tracker.can_retry(phase, iteration):
            retry_count = self.error_recovery_tracker.get_retry_count(phase, iteration)
            QMessageBox.critical(
                self, "Too Many Retries",
                f"Maximum retry attempts ({retry_count}) reached for this phase. "
                "Please choose Skip or Send to LLM instead."
            )
            self._show_error_recovery_dialog(error_info)
            return

        self.error_recovery_tracker.record_retry(phase, iteration)
        retry_count = self.error_recovery_tracker.get_retry_count(phase, iteration)
        self.log_viewer.append_log(
            f"Retry attempt {retry_count} of 3 for {phase.name}",
            "warning"
        )
        self.retry_current_phase()

    def _handle_error_skip(self, error_info):
        """Handle skip to next iteration action."""
        self.skip_to_next_iteration()

    def _handle_error_send_to_llm(self, error_info, provider_name: str):
        """Handle send to LLM for fixing action."""
        from ..workers.error_fix_worker import ErrorFixWorker

        self.log_viewer.append_log(
            f"Sending error to {provider_name} for analysis...",
            "info"
        )

        model = self.state_machine.context.llm_config.get(f"{provider_name}_model")

        worker = ErrorFixWorker(error_info, provider_name, model)
        self._connect_worker_signals(worker)
        worker.signals.result.connect(
            lambda result: self._on_error_fix_complete(result, error_info)
        )

        self.current_worker = worker
        self.thread_pool.start(worker)

    def _on_error_fix_complete(self, result: dict, error_info):
        """Handle completion of LLM error fix attempt."""
        from .dialogs.error_conclusion_dialog import ErrorConclusionDialog

        conclusion = result.get("conclusion", "")
        provider_name = result.get("provider_name", "LLM")

        # Show conclusion dialog
        dialog = ErrorConclusionDialog(self, conclusion, provider_name)

        dialog.retry_requested.connect(lambda: self._handle_conclusion_retry(error_info))
        dialog.try_different_llm_requested.connect(lambda: self._handle_conclusion_try_different_llm(error_info))
        dialog.skip_requested.connect(lambda: self._handle_conclusion_skip(error_info))

        dialog.exec()

    def _handle_conclusion_retry(self, error_info):
        """Handle retry after LLM fix conclusion."""
        # Reset retry count since LLM made changes
        self.error_recovery_tracker.reset_phase(
            error_info.phase,
            error_info.current_iteration
        )
        self.log_viewer.append_log("Retrying phase after LLM fix...", "info")
        self.retry_current_phase()

    def _handle_conclusion_try_different_llm(self, error_info):
        """Handle trying a different LLM after conclusion."""
        self.log_viewer.append_log("Returning to error recovery to try different LLM...", "info")
        self._show_error_recovery_dialog(error_info)

    def _handle_conclusion_skip(self, error_info):
        """Handle skip after LLM fix conclusion."""
        self.log_viewer.append_log("Skipping to next iteration...", "info")
        self.skip_to_next_iteration()

    # =========================================================================
    # Client Message Processing Methods
    # =========================================================================

    def _process_client_messages(self):
        """Process all pending client messages sequentially."""
        ctx = self.state_machine.context

        if not ctx.pending_client_messages:
            # No messages - continue to task checking
            self._continue_after_messages()
            return

        # Pop first message from queue
        message_data = ctx.pending_client_messages[0]

        # Update status in UI
        self.chat_panel.update_message_status(message_data["id"], "processing")
        self.log_viewer.append_log(f"Processing client message: {message_data['content'][:50]}...", "info")

        # Create worker
        from ..workers.client_message_worker import ClientMessageWorker

        worker = ClientMessageWorker(
            message=message_data["content"],
            provider_name=ctx.llm_config.get("client_message_handler", "gemini"),
            working_directory=ctx.working_directory,
            model=ctx.llm_config.get("client_message_handler_model"),
            debug_mode=ctx.debug_mode_enabled,
            debug_breakpoints=ctx.debug_breakpoints,
            show_terminal=ctx.show_llm_terminals,
            update_description=message_data.get("update_description"),
            add_tasks=message_data.get("add_tasks"),
            provide_answer=message_data.get("provide_answer")
        )

        # Connect signals
        self._connect_worker_signals(worker)
        worker.signals.result.connect(self.on_client_message_complete)

        # Store message ID for result handling
        self._current_message_id = message_data["id"]

        self.current_worker = worker
        self.thread_pool.start(worker)

    @Slot(object)
    def on_client_message_complete(self, result: dict):
        """Handle client message processing completion."""
        ctx = self.state_machine.context

        # Remove processed message from queue
        if ctx.pending_client_messages:
            ctx.pending_client_messages.pop(0)

        # Update status in UI
        self.chat_panel.update_message_status(self._current_message_id, "completed")

        # Track what was updated
        description_updated = False
        tasks_updated = False

        # Check if description was updated (reload from file)
        if self.file_manager:
            new_description = self._load_description_from_file()
            if new_description != ctx.description:
                description_updated = True
                self.log_viewer.append_log("Product description updated from chat message", "info")

                # Update description in UI
                self._suppress_description_sync = True
                try:
                    self.description_panel.set_description(new_description)
                finally:
                    self._suppress_description_sync = False

                # Update state machine
                self.state_machine.update_context(description=new_description)
                self._update_floating_start_button_visibility()

            # Check if tasks were updated
            old_tasks = ctx.tasks_content
            new_tasks = self.file_manager.read_tasks()
            if new_tasks != old_tasks:
                tasks_updated = True
                self.log_viewer.append_log("Tasks updated from chat message", "info")
                # Update context and UI
                self.state_machine.update_context(tasks_content=new_tasks)
                # Update button states to reflect new task status
                self.update_button_states()

        # If answer was provided, show it to user
        if result.get("has_answer"):
            answer_content = result.get("answer_content", "")
            self.log_viewer.append_log("LLM provided an answer to client message", "info")

            # Update chat panel with answer
            self.chat_panel.add_answer(self._current_message_id, answer_content)

            # Show modal dialog with answer
            from ..dialogs.answer_display_dialog import AnswerDisplayDialog
            dialog = AnswerDisplayDialog(answer_content, parent=self)
            dialog.exec()
        else:
            # No direct answer - LLM chose to update files instead
            # Build status message
            status_parts = []
            if description_updated:
                status_parts.append("Updated product description")
            if tasks_updated:
                status_parts.append("Updated tasks")

            if status_parts:
                status_message = " and ".join(status_parts)
                self.log_viewer.append_log(f"Client message processed - {status_message}", "info")
                # Add the status as an "answer" in the chat panel
                self.chat_panel.add_answer(self._current_message_id, status_message)
            else:
                self.log_viewer.append_log("Client message processed - no changes detected", "info")

        # Process next message or continue workflow
        if ctx.pending_client_messages:
            # More messages - process next
            self._process_client_messages()
        else:
            # All messages processed - continue to task checking
            self._continue_after_messages()

    def _continue_after_messages(self):
        """Continue workflow after all client messages processed."""
        from ..utils.markdown_parser import has_incomplete_tasks
        ctx = self.state_machine.context
        phase = self.state_machine.phase

        # If we're in an active workflow iteration, continue the loop
        if phase in [Phase.MAIN_EXECUTION, Phase.DEBUG_REVIEW, Phase.GIT_OPERATIONS]:
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
        else:
            # Not in an active iteration - messages were processed outside workflow
            self.log_viewer.append_log("Client messages processed.", "info")
