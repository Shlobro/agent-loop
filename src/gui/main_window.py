"""Main application window."""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QPushButton, QMessageBox, QApplication
)
from PySide6.QtCore import Qt, Slot, QThreadPool

from .widgets.description_panel import DescriptionPanel
from .widgets.question_panel import QuestionPanel
from .widgets.llm_selector_panel import LLMSelectorPanel
from .widgets.config_panel import ConfigPanel, ExecutionConfig
from .widgets.log_viewer import LogViewer
from .widgets.status_panel import StatusPanel
from .dialogs.git_approval_dialog import GitApprovalDialog

from ..core.state_machine import StateMachine, Phase, SubPhase
from ..core.file_manager import FileManager
from ..core.session_manager import SessionManager

from ..workers.question_worker import QuestionWorker
from ..workers.planning_worker import PlanningWorker
from ..workers.execution_worker import ExecutionWorker
from ..workers.review_worker import ReviewWorker
from ..workers.git_worker import GitWorker

# Import llm module to register providers
from .. import llm


class MainWindow(QMainWindow):
    """
    Primary application window containing all panels and orchestrating
    the interaction between UI components and worker threads.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AgentHarness - Autonomous Code Generator")
        self.setMinimumSize(1200, 800)

        # Thread pool for worker management
        self.thread_pool = QThreadPool()

        # Core components
        self.state_machine = StateMachine()
        self.file_manager = None  # Created when working dir is set
        self.session_manager = SessionManager()

        # Current worker reference (for cancellation)
        self.current_worker = None

        # Session preferences
        self.remember_push_choice = False
        self.auto_push_remembered = False

        # Setup UI
        self.setup_ui()
        self.connect_signals()
        self.update_button_states()

    def setup_ui(self):
        """Initialize and layout all UI components."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Status bar at top
        self.status_panel = StatusPanel()
        main_layout.addWidget(self.status_panel)

        # Main content area: Two columns (Logs left, Rest right)
        main_splitter = QSplitter(Qt.Horizontal)

        # LEFT COLUMN: Log viewer
        self.log_viewer = LogViewer()
        main_splitter.addWidget(self.log_viewer)

        # RIGHT COLUMN: Everything else
        right_column = QWidget()
        right_column_layout = QVBoxLayout(right_column)
        right_column_layout.setContentsMargins(0, 0, 0, 0)

        # Top section of right column: Description + Config/LLM
        top_splitter = QSplitter(Qt.Horizontal)

        # Description panel
        self.description_panel = DescriptionPanel()
        top_splitter.addWidget(self.description_panel)

        # Config and LLM selection side by side
        config_widget = QWidget()
        config_layout = QVBoxLayout(config_widget)
        config_layout.setContentsMargins(0, 0, 0, 0)

        self.llm_selector_panel = LLMSelectorPanel()
        config_layout.addWidget(self.llm_selector_panel)

        self.config_panel = ConfigPanel()
        config_layout.addWidget(self.config_panel)

        config_layout.addStretch()
        top_splitter.addWidget(config_widget)

        # Set top splitter sizes (60% description, 40% config)
        top_splitter.setSizes([500, 350])

        right_column_layout.addWidget(top_splitter, stretch=1)

        # Bottom section of right column: Clarifying Questions (larger)
        self.question_panel = QuestionPanel()
        self.question_panel.setMinimumHeight(300)
        right_column_layout.addWidget(self.question_panel, stretch=2)

        # Control buttons at bottom of right column
        button_layout = QHBoxLayout()

        self.start_button = QPushButton("Start")
        self.start_button.setMinimumWidth(100)
        self.start_button.clicked.connect(self.on_start_clicked)
        button_layout.addWidget(self.start_button)

        self.pause_button = QPushButton("Pause")
        self.pause_button.setMinimumWidth(100)
        self.pause_button.clicked.connect(self.on_pause_clicked)
        self.pause_button.setEnabled(False)
        button_layout.addWidget(self.pause_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setMinimumWidth(100)
        self.stop_button.clicked.connect(self.on_stop_clicked)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)

        button_layout.addStretch()

        right_column_layout.addLayout(button_layout)

        main_splitter.addWidget(right_column)

        # Set main splitter sizes (40% logs, 60% rest)
        main_splitter.setSizes([480, 720])

        main_layout.addWidget(main_splitter, stretch=1)

    def connect_signals(self):
        """Connect UI signals to slots."""
        # State machine signals
        self.state_machine.phase_changed.connect(self.on_phase_changed)
        self.state_machine.workflow_completed.connect(self.on_workflow_completed)

        # Question panel
        self.question_panel.answers_submitted.connect(self.on_answers_submitted)

        # Config panel
        self.config_panel.working_directory_changed.connect(self.on_working_dir_changed)

    def update_button_states(self):
        """Update button enabled states based on current phase."""
        phase = self.state_machine.phase

        is_idle = phase == Phase.IDLE
        is_running = phase not in (Phase.IDLE, Phase.COMPLETED, Phase.ERROR,
                                   Phase.CANCELLED, Phase.PAUSED, Phase.AWAITING_ANSWERS)
        is_paused = phase == Phase.PAUSED
        is_awaiting = phase == Phase.AWAITING_ANSWERS

        self.start_button.setEnabled(is_idle or is_paused)
        self.start_button.setText("Resume" if is_paused else "Start")

        self.pause_button.setEnabled(is_running)
        self.stop_button.setEnabled(is_running or is_paused or is_awaiting)

        # Also update panel states
        self.description_panel.set_readonly(not is_idle)
        self.llm_selector_panel.set_enabled(is_idle)
        self.config_panel.set_enabled(is_idle)

    @Slot()
    def on_start_clicked(self):
        """Begin or resume the workflow."""
        if self.state_machine.phase == Phase.PAUSED:
            # Resume from pause
            self.resume_workflow()
        else:
            # Start new workflow
            self.start_workflow()

    def start_workflow(self):
        """Start a new workflow from the beginning."""
        # Validate inputs
        if self.description_panel.is_empty():
            QMessageBox.warning(self, "Missing Description",
                                "Please enter a project description.")
            return

        if not self.config_panel.has_valid_working_directory():
            QMessageBox.warning(self, "Missing Working Directory",
                                "Please select a valid working directory.")
            return

        # Initialize state
        working_dir = self.config_panel.get_working_directory()
        config = self.config_panel.get_config()
        llm_config = self.llm_selector_panel.get_config_dict()

        self.state_machine.update_context(
            description=self.description_panel.get_description(),
            working_directory=working_dir,
            max_iterations=config.max_main_iterations,
            debug_iterations=config.debug_loop_iterations,
            auto_push=config.auto_push,
            llm_config=llm_config
        )

        # Initialize file manager
        self.file_manager = FileManager(working_dir)
        self.session_manager.set_working_directory(working_dir)

        # Clear log
        self.log_viewer.clear()
        self.log_viewer.append_log("Starting workflow...", "info")

        # Start Phase 1: Question Generation
        self.state_machine.transition_to(Phase.QUESTION_GENERATION)
        self.run_question_generation()

    def resume_workflow(self):
        """Resume from paused state."""
        if not self.state_machine.resume():
            self.log_viewer.append_log("Failed to resume workflow", "error")
            return

        self.log_viewer.append_log("Resuming workflow...", "info")

        # Resume the appropriate worker based on phase
        phase = self.state_machine.phase
        if phase == Phase.MAIN_EXECUTION:
            self.run_main_execution()
        elif phase == Phase.DEBUG_REVIEW:
            self.run_review_loop()
        elif phase == Phase.GIT_OPERATIONS:
            self.run_git_operations()

    @Slot()
    def on_pause_clicked(self):
        """Pause the current workflow."""
        self.log_viewer.append_log("Pause requested...", "warning")
        self.state_machine.request_pause()

        if self.current_worker:
            self.current_worker.pause()

        # Save session
        try:
            self.session_manager.save_session(self.state_machine)
            self.log_viewer.append_log("Session saved", "info")
        except Exception as e:
            self.log_viewer.append_log(f"Failed to save session: {e}", "error")

    @Slot()
    def on_stop_clicked(self):
        """Stop the current workflow."""
        reply = QMessageBox.question(
            self, "Stop Workflow",
            "Are you sure you want to stop? Progress will be lost.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.log_viewer.append_log("Stopping workflow...", "warning")
            self.state_machine.request_stop()

            if self.current_worker:
                self.current_worker.cancel()

            self.state_machine.transition_to(Phase.CANCELLED)

    @Slot(object, object)
    def on_phase_changed(self, phase: Phase, sub_phase: SubPhase):
        """Handle phase change."""
        phase_name = self.state_machine.get_phase_display_name()
        sub_name = self.state_machine.get_sub_phase_display_name()

        self.status_panel.set_phase(phase_name)
        if sub_name:
            self.status_panel.set_sub_status(sub_name)

        self.log_viewer.append_phase(phase_name)
        self.update_button_states()

    @Slot(bool)
    def on_workflow_completed(self, success: bool):
        """Handle workflow completion."""
        if success:
            self.log_viewer.append_success("Workflow completed successfully!")
            QMessageBox.information(self, "Complete", "Workflow completed successfully!")
        else:
            phase = self.state_machine.phase
            if phase == Phase.ERROR:
                error = self.state_machine.context.error_message or "Unknown error"
                self.log_viewer.append_error(f"Workflow failed: {error}")
            elif phase == Phase.CANCELLED:
                self.log_viewer.append_warning("Workflow cancelled")

        self.update_button_states()
        self.status_panel.set_running(False)

    @Slot(str)
    def on_working_dir_changed(self, path: str):
        """Handle working directory change."""
        if path:
            self.session_manager.set_working_directory(path)

            # Check for existing session
            if self.session_manager.has_saved_session():
                info = self.session_manager.get_session_info()
                if info:
                    reply = QMessageBox.question(
                        self, "Resume Session?",
                        f"Found saved session from {info.get('saved_at', 'unknown')}.\n"
                        f"Phase: {info.get('phase', 'unknown')}, "
                        f"Iteration: {info.get('iteration', 0)}\n\n"
                        "Would you like to resume it?",
                        QMessageBox.Yes | QMessageBox.No
                    )

                    if reply == QMessageBox.Yes:
                        self.load_saved_session()

    def load_saved_session(self):
        """Load and restore a saved session."""
        try:
            self.session_manager.load_session(self.state_machine)
            ctx = self.state_machine.context

            # Restore UI state
            self.description_panel.set_description(ctx.description)
            self.llm_selector_panel.set_config(ctx.llm_config)
            self.config_panel.set_config(ExecutionConfig(
                max_main_iterations=ctx.max_iterations,
                debug_loop_iterations=ctx.debug_iterations,
                auto_push=ctx.auto_push,
                working_directory=ctx.working_directory
            ))

            self.file_manager = FileManager(ctx.working_directory)

            self.log_viewer.append_log("Session restored", "success")
            self.update_button_states()

        except Exception as e:
            self.log_viewer.append_error(f"Failed to load session: {e}")

    @Slot(dict)
    def on_answers_submitted(self, answers: dict):
        """Handle question answers submission."""
        self.log_viewer.append_log(f"Received {len(answers)} answers", "info")
        self.state_machine.update_context(answers=answers)

        # Move to task planning
        self.state_machine.transition_to(Phase.TASK_PLANNING)
        self.run_task_planning()

    # =========================================================================
    # Worker execution methods
    # =========================================================================

    def run_question_generation(self):
        """Run Phase 1: Question Generation."""
        ctx = self.state_machine.context

        worker = QuestionWorker(
            description=ctx.description,
            provider_name=ctx.llm_config.get("question_gen", "claude"),
            working_directory=ctx.working_directory
        )

        self._connect_worker_signals(worker)
        worker.signals.questions_ready.connect(self.on_questions_ready)

        self.current_worker = worker
        self.thread_pool.start(worker)

    @Slot(dict)
    def on_questions_ready(self, questions: dict):
        """Handle generated questions."""
        self.question_panel.load_questions(questions)
        self.state_machine.update_context(questions_json=questions)
        self.state_machine.transition_to(Phase.AWAITING_ANSWERS)
        self.log_viewer.append_success(f"Generated {len(questions.get('questions', []))} questions")

    def run_task_planning(self):
        """Run Phase 2: Task Planning."""
        ctx = self.state_machine.context

        worker = PlanningWorker(
            description=ctx.description,
            answers=ctx.answers,
            provider_name=ctx.llm_config.get("task_planning", "claude"),
            working_directory=ctx.working_directory
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

        # Move to main execution
        self.state_machine.transition_to(Phase.MAIN_EXECUTION)
        self.run_main_execution()

    def run_main_execution(self):
        """Run Phase 3: Main Execution Loop."""
        ctx = self.state_machine.context

        worker = ExecutionWorker(
            provider_name=ctx.llm_config.get("coder", "claude"),
            working_directory=ctx.working_directory,
            max_iterations=ctx.max_iterations,
            start_iteration=ctx.current_iteration
        )

        self._connect_worker_signals(worker)
        worker.signals.iteration_complete.connect(self.on_iteration_complete)
        worker.signals.result.connect(self.on_execution_complete)

        self.current_worker = worker
        self.thread_pool.start(worker)

    @Slot(int)
    def on_iteration_complete(self, iteration: int):
        """Handle iteration completion."""
        ctx = self.state_machine.context
        self.state_machine.update_context(current_iteration=iteration)
        self.status_panel.set_iteration(iteration, ctx.max_iterations)

    @Slot(object)
    def on_execution_complete(self, result: dict):
        """Handle main execution completion."""
        if result.get("stopped_early"):
            if self.state_machine.context.pause_requested:
                self.state_machine.transition_to(Phase.PAUSED)
            return

        # Check if we should run review loop
        if self.state_machine.context.debug_iterations > 0:
            self.state_machine.transition_to(Phase.DEBUG_REVIEW)
            self.run_review_loop()
        else:
            # Skip to git
            self.state_machine.transition_to(Phase.GIT_OPERATIONS)
            self.run_git_operations()

    def run_review_loop(self):
        """Run Phase 4: Debug/Review Loop."""
        ctx = self.state_machine.context

        worker = ReviewWorker(
            reviewer_provider_name=ctx.llm_config.get("reviewer", "claude"),
            fixer_provider_name=ctx.llm_config.get("fixer", "claude"),
            working_directory=ctx.working_directory,
            iterations=ctx.debug_iterations,
            start_iteration=ctx.current_debug_iteration
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
        self.status_panel.set_sub_status(f"Completed: {review_type.replace('_', ' ').title()}")

    @Slot(object)
    def on_review_loop_complete(self, result: dict):
        """Handle review loop completion."""
        if result.get("stopped_early"):
            if self.state_machine.context.pause_requested:
                self.state_machine.transition_to(Phase.PAUSED)
            return

        # Move to git operations
        self.state_machine.transition_to(Phase.GIT_OPERATIONS)
        self.run_git_operations()

    def run_git_operations(self):
        """Run Phase 5: Git Operations."""
        ctx = self.state_machine.context
        auto_push = ctx.auto_push

        # If not auto-push and we remember choice, use that
        if not auto_push and self.remember_push_choice:
            auto_push = self.auto_push_remembered

        # If still not auto-push, ask user
        if not auto_push and not self.remember_push_choice:
            should_push, remember = GitApprovalDialog.get_approval(self)
            if remember:
                self.remember_push_choice = True
                self.auto_push_remembered = should_push
            auto_push = should_push

        worker = GitWorker(
            provider_name=ctx.llm_config.get("git_ops", "claude"),
            working_directory=ctx.working_directory,
            auto_push=auto_push
        )

        self._connect_worker_signals(worker)
        worker.signals.result.connect(self.on_git_complete)

        self.current_worker = worker
        self.thread_pool.start(worker)

    @Slot(object)
    def on_git_complete(self, result: dict):
        """Handle git operations completion."""
        if result.get("committed"):
            self.log_viewer.append_success("Changes committed")
        if result.get("pushed"):
            self.log_viewer.append_success("Changes pushed to remote")

        # Clean up session file
        try:
            self.session_manager.delete_session()
        except Exception:
            pass

        self.state_machine.transition_to(Phase.COMPLETED)

    def _connect_worker_signals(self, worker):
        """Connect common worker signals."""
        worker.signals.log.connect(self.log_viewer.append_log)
        worker.signals.llm_output.connect(self.log_viewer.append_llm_output)
        worker.signals.status.connect(self.status_panel.set_sub_status)
        worker.signals.error.connect(self.on_worker_error)
        worker.signals.finished.connect(self.on_worker_finished)

    @Slot(tuple)
    def on_worker_error(self, error_info):
        """Handle worker error."""
        exc_type, exc_value, tb_str = error_info
        self.log_viewer.append_error(f"Error: {exc_value}")
        self.state_machine.set_error(str(exc_value))

    @Slot()
    def on_worker_finished(self):
        """Handle worker completion."""
        self.current_worker = None

    def closeEvent(self, event):
        """Handle window close."""
        # Check if workflow is running
        if self.state_machine.phase not in (Phase.IDLE, Phase.COMPLETED,
                                             Phase.ERROR, Phase.CANCELLED):
            reply = QMessageBox.question(
                self, "Workflow Running",
                "A workflow is still running. Do you want to quit anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.No:
                event.ignore()
                return

            # Cancel current worker
            if self.current_worker:
                self.current_worker.cancel()

        event.accept()
