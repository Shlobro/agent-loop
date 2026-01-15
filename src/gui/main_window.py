"""Main application window."""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QPushButton, QMessageBox, QApplication, QFileDialog
)
from PySide6.QtCore import Qt, Slot, QThreadPool
from PySide6.QtGui import QAction

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
from ..core.project_settings import ProjectSettings, ProjectSettingsManager
from ..core.question_prefetch_manager import QuestionPrefetchManager

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
        self.question_prefetch_manager = QuestionPrefetchManager(self.thread_pool)

        # Current worker reference (for cancellation)
        self.current_worker = None

        # Session preferences
        self.remember_push_choice = False
        self.auto_push_remembered = False

        # Activity panel state
        self.activity_state = {
            "phase": "",
            "action": "",
            "agent": "",
            "review": "",
            "findings": "",
        }
        self._last_phase = None

        # Setup UI
        self.setup_menu_bar()
        self.setup_ui()
        self.connect_signals()
        self.update_button_states()

    def setup_menu_bar(self):
        """Initialize the menu bar with File menu."""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("&File")

        # Save Settings action
        save_action = QAction("&Save Settings...", self)
        save_action.setShortcut("Ctrl+S")
        save_action.setStatusTip("Save current project settings to file")
        save_action.triggered.connect(self.on_save_settings)
        file_menu.addAction(save_action)

        # Load Settings action
        load_action = QAction("&Load Settings...", self)
        load_action.setShortcut("Ctrl+O")
        load_action.setStatusTip("Load project settings from file")
        load_action.triggered.connect(self.on_load_settings)
        file_menu.addAction(load_action)

        file_menu.addSeparator()

        # Exit action
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("Exit the application")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

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
        self.question_panel.answer_submitted.connect(self.on_single_answer_submitted)
        self.question_panel.stop_requested.connect(self.on_stop_questions_requested)
        self.question_panel.request_more_questions.connect(self.on_request_more_questions)
        self.question_panel.start_planning_requested.connect(self.on_start_planning_requested)

        # Question prefetch manager
        self.question_prefetch_manager.question_ready.connect(self.on_prefetch_question_ready)
        self.question_prefetch_manager.log_message.connect(self.log_viewer.append_log)

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

    def _reset_activity_state(self):
        """Clear activity panel state for a fresh run."""
        self.activity_state = {
            "phase": "",
            "action": "",
            "agent": "",
            "review": "",
            "findings": "",
        }
        self._last_phase = None

    def _should_show_activity(self, phase: Phase) -> bool:
        """Return True if the activity panel should be visible for this phase."""
        return phase not in (Phase.IDLE, Phase.QUESTION_GENERATION, Phase.AWAITING_ANSWERS)

    def _get_agent_label(self, phase: Phase) -> str:
        """Build a compact agent label for the current phase."""
        ctx = self.state_machine.context
        config = ctx.llm_config
        if phase == Phase.TASK_PLANNING:
            return f"Planner: {config.get('task_planning', 'N/A')}"
        if phase == Phase.MAIN_EXECUTION:
            return f"Coder: {config.get('coder', 'N/A')}"
        if phase == Phase.DEBUG_REVIEW:
            return f"Reviewer: {config.get('reviewer', 'N/A')}"
        if phase in (Phase.GIT_OPERATIONS, Phase.AWAITING_GIT_APPROVAL):
            return f"Git Ops: {config.get('git_ops', 'N/A')}"
        return ""

    def _refresh_activity_panel(self):
        """Render the activity panel with the current activity state."""
        if not self._should_show_activity(self.state_machine.phase):
            return
        self.question_panel.show_activity(
            phase=self.activity_state.get("phase", ""),
            action=self.activity_state.get("action", ""),
            agent=self.activity_state.get("agent", ""),
            review=self.activity_state.get("review", ""),
            findings=self.activity_state.get("findings", ""),
        )

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
            max_questions=config.max_questions,
            current_question_num=0,
            qa_pairs=[],
            current_question_text="",
            current_question_options=[],
            answers={},
            auto_push=config.auto_push,
            git_remote=config.git_remote,
            review_types=config.review_types,
            llm_config=llm_config
        )
        self._reset_activity_state()

        # Initialize file manager
        self.file_manager = FileManager(working_dir)
        self.session_manager.set_working_directory(working_dir)

        # Clear log
        self.log_viewer.clear()
        self.log_viewer.append_log("Starting workflow...", "info")
        self.log_viewer.append_log("=" * 50, "info")
        self.log_viewer.append_log("WORKFLOW CONFIGURATION:", "info")
        self.log_viewer.append_log(f"  Working Directory: {working_dir}", "info")
        self.log_viewer.append_log(f"  Max Main Iterations: {config.max_main_iterations}", "info")
        self.log_viewer.append_log(f"  Max Questions: {config.max_questions}", "info")
        self.log_viewer.append_log(f"  Debug Loop Iterations: {config.debug_loop_iterations}", "info")
        review_types = config.review_types or []
        review_labels = ", ".join([r.replace('_', ' ').title() for r in review_types]) or "(none)"
        self.log_viewer.append_log(f"  Review Types: {review_labels}", "info")
        self.log_viewer.append_log(f"  Auto Push: {config.auto_push}", "info")
        self.log_viewer.append_log(f"  Git Remote: {config.git_remote or '(not set)'}", "info")
        self.log_viewer.append_log("LLM PROVIDERS:", "info")
        self.log_viewer.append_log(f"  Question Gen: {llm_config.get('question_gen', 'N/A')}", "info")
        self.log_viewer.append_log(f"  Task Planning: {llm_config.get('task_planning', 'N/A')}", "info")
        self.log_viewer.append_log(f"  Coder: {llm_config.get('coder', 'N/A')}", "info")
        self.log_viewer.append_log(f"  Reviewer: {llm_config.get('reviewer', 'N/A')}", "info")
        self.log_viewer.append_log(f"  Fixer: {llm_config.get('fixer', 'N/A')}", "info")
        self.log_viewer.append_log(f"  Git Ops: {llm_config.get('git_ops', 'N/A')}", "info")
        self.log_viewer.append_log("=" * 50, "info")

        # Start Phase 1: Question Generation (or skip if max_questions is 0)
        if config.max_questions == 0:
            reply = QMessageBox.question(
                self,
                "No Clarifying Questions",
                "Not allowing the Agent to ask any questions means the quality of the output will not be as good.\n"
                "Do you want to begin planning anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                self.log_viewer.append_log("User cancelled start after max questions warning.", "info")
                return

            self.log_viewer.append_log("Max questions set to 0 - skipping question phase.", "warning")
            self.question_panel.clear_question()
            self.question_panel.set_readonly(True)
            self.state_machine.transition_to(Phase.QUESTION_GENERATION)
            self._finish_question_phase()
            return

        self.question_panel.clear_question()
        self.question_panel.set_readonly(True)
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
        elif phase == Phase.QUESTION_GENERATION:
            self.run_question_generation()
        elif phase == Phase.AWAITING_ANSWERS:
            self._restore_question_ui()

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
        phase_changed = phase != self._last_phase
        self._last_phase = phase

        self.status_panel.set_phase(phase_name)
        if sub_name:
            self.status_panel.set_sub_status(sub_name)

        self.log_viewer.append_phase(phase_name)
        self.update_button_states()

        if self._should_show_activity(phase):
            if phase_changed:
                self.activity_state["phase"] = phase_name
                self.activity_state["action"] = ""
                self.activity_state["review"] = ""
                self.activity_state["findings"] = ""
            else:
                self.activity_state["phase"] = phase_name
            self.activity_state["agent"] = self._get_agent_label(phase)
            if sub_name and not self.activity_state["action"]:
                self.activity_state["action"] = sub_name
            self._refresh_activity_panel()

    @Slot(str)
    def on_worker_status(self, status: str):
        """Handle worker status updates for UI panels."""
        self.status_panel.set_sub_status(status)

        if not self._should_show_activity(self.state_machine.phase):
            return

        self.activity_state["action"] = status

        if self.state_machine.phase == Phase.DEBUG_REVIEW:
            ctx = self.state_machine.context
            if status.startswith("Fixing:"):
                self.activity_state["agent"] = f"Fixer: {ctx.llm_config.get('fixer', 'N/A')}"
            elif status.startswith("Review:"):
                self.activity_state["agent"] = f"Reviewer: {ctx.llm_config.get('reviewer', 'N/A')}"
                review_name = status.replace("Review:", "").strip()
                if review_name:
                    self.activity_state["review"] = review_name
                    self.activity_state["findings"] = ""

        self._refresh_activity_panel()

    @Slot(str, int)
    def on_review_summary(self, review_type: str, issue_count: int):
        """Show review findings in the activity panel as they arrive."""
        if not self._should_show_activity(self.state_machine.phase):
            return

        review_name = review_type.replace('_', ' ').title()
        self.activity_state["review"] = review_name
        if issue_count <= 0:
            self.activity_state["findings"] = "No issues"
        else:
            self.activity_state["findings"] = f"{issue_count} issue(s)"
        self._refresh_activity_panel()

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
                working_directory=ctx.working_directory,
                git_remote=ctx.git_remote,
                max_questions=ctx.max_questions
            ))

            self.file_manager = FileManager(ctx.working_directory)

            self.log_viewer.append_log("Session restored", "success")
            if self.state_machine.phase == Phase.AWAITING_ANSWERS:
                self._restore_question_ui()
            self.update_button_states()

        except Exception as e:
            self.log_viewer.append_error(f"Failed to load session: {e}")

    def _validate_answer(self, question_text: str, answer: str) -> tuple[bool, str]:
        """
        Validate question and answer without side effects.

        Args:
            question_text: The question text (can be empty, will use ctx.current_question_text)
            answer: The user's answer

        Returns:
            tuple[bool, str]: (is_valid, error_message)
                - (True, "") if valid
                - (False, error_msg) if invalid
        """
        ctx = self.state_machine.context
        question = question_text or ctx.current_question_text

        # Validate question text
        if not question:
            return False, "No question text available for answer submission"

        # Validate answer is not empty
        if not answer or not answer.strip():
            return False, "Cannot submit empty answer"

        return True, ""

    def _commit_answer(self, question_text: str, answer: str):
        """
        Commit a validated answer to state (assumes validation already passed).

        This method performs all state mutations for recording an answer.
        Should only be called after _validate_answer returns True.

        Args:
            question_text: The question text (can be empty, will use ctx.current_question_text)
            answer: The user's answer
        """
        ctx = self.state_machine.context
        question = question_text or ctx.current_question_text

        # Record the answer in prefetch manager
        self.question_prefetch_manager.on_answer_submitted(question, answer)

        # Update state
        qa_pairs = list(ctx.qa_pairs)
        qa_pairs.append({
            "question": question,
            "answer": answer
        })

        next_num = ctx.current_question_num + 1
        self.state_machine.update_context(
            qa_pairs=qa_pairs,
            current_question_num=next_num,
            current_question_text="",
            current_question_options=[]
        )

        self.question_panel.show_previous_qa(qa_pairs)
        self.log_viewer.append_log(f"Recorded answer {next_num}/{ctx.max_questions}", "info")

    def _process_answer(self, question_text: str, answer: str) -> bool:
        """
        Validate and commit a question answer.

        This is a convenience method that combines validation and commit.
        For atomic operations, use _validate_answer + _commit_answer separately.

        Args:
            question_text: The question text (can be empty, will use ctx.current_question_text)
            answer: The user's answer

        Returns:
            bool: True if successfully processed, False if validation failed
        """
        is_valid, error_msg = self._validate_answer(question_text, answer)
        if not is_valid:
            self.log_viewer.append_log(error_msg, "warning")
            return False

        self._commit_answer(question_text, answer)
        return True

    @Slot(str, str)
    def on_single_answer_submitted(self, question_text: str, answer: str):
        """Handle a single question answer submission (Submit Answer button)."""
        ctx = self.state_machine.context

        # Process the answer using shared logic
        if not self._process_answer(question_text, answer):
            return

        next_num = ctx.current_question_num

        # Check if we've now reached max questions after processing this answer
        # If so, wait for user decision (don't auto-proceed to planning)
        if next_num >= ctx.max_questions:
            self.log_viewer.append_log(
                f"Reached max questions ({ctx.max_questions}). Waiting for user to request more or start planning...",
                "info"
            )
            # Show waiting state with decision buttons
            self.question_panel.show_waiting_for_decision(ctx.qa_pairs, ctx.max_questions)
            self.state_machine.update_context(is_last_question_shown=True)
            return

        # Show the next buffered question
        self.question_panel.set_readonly(True)
        self._show_next_buffered_question()

    @Slot()
    def on_stop_questions_requested(self):
        """Handle user request to stop question loop early."""
        self.log_viewer.append_log("User stopped question loop early", "info")
        # Cancel any pending prefetch operations
        self.question_prefetch_manager.cancel()
        self._finish_question_phase()

    @Slot(str, str)
    def on_request_more_questions(self, question_text: str, answer: str):
        """Handle user request for more questions.

        Can be called either:
        1. From a question (answer required)
        2. From waiting state after max questions (no answer needed)

        Args:
            question_text: The current question text (empty if in waiting mode)
            answer: The user's answer to the current question (empty if in waiting mode)
        """
        ctx = self.state_machine.context

        self.log_viewer.append_log("User requested more questions", "info")

        # Increase max questions limit
        new_max = ctx.max_questions + 5
        self.state_machine.update_context(
            max_questions=new_max,
            is_last_question_shown=False
        )
        self.question_prefetch_manager.max_questions = new_max
        self.log_viewer.append_log(f"Increased question limit to {new_max}", "info")

        # Ensure buffer is being filled (this will start workers if needed)
        self.question_prefetch_manager.ensure_generating()

        # Update UI state
        self.question_panel.set_readonly(True)

        # Show next question if available, otherwise show generating message
        self._show_next_buffered_question()

    @Slot(str, str)
    def on_start_planning_requested(self, question_text: str, answer: str):
        """Handle user request to start planning.

        Can be called either:
        1. From a question (answer required)
        2. From waiting state after max questions (no answer needed)

        Args:
            question_text: The current question text (empty if in waiting mode)
            answer: The user's answer to the current question (empty if in waiting mode)
        """
        self.log_viewer.append_log("User requested to start planning", "info")

        # Cancel any pending prefetch operations
        self.question_prefetch_manager.cancel()

        # Move directly to planning phase
        self._finish_question_phase()

    # =========================================================================
    # Worker execution methods
    # =========================================================================

    def run_question_generation(self):
        """Run Phase 1: Question Generation (with prefetching)."""
        ctx = self.state_machine.context

        # Initialize prefetch manager
        self.question_prefetch_manager.initialize(
            description=ctx.description,
            provider_name=ctx.llm_config.get("question_gen", "claude"),
            working_directory=ctx.working_directory,
            model=ctx.llm_config.get("question_gen_model"),
            max_questions=ctx.max_questions
        )

        # Start prefetching initial batch of questions
        self.log_viewer.append_log("Starting question generation with prefetching...", "info")
        self.question_prefetch_manager.start_prefetching()
        self.question_panel.show_generating_message()
        self.question_panel.show_previous_qa(ctx.qa_pairs)

        # Transition to awaiting state - we'll show the first question when it's ready
        self.state_machine.transition_to(Phase.QUESTION_GENERATION, SubPhase.GENERATING_SINGLE_QUESTION)

    def _show_next_buffered_question(self):
        """Show the next question from the buffer."""
        ctx = self.state_machine.context

        # Check if we have a buffered question
        if not self.question_prefetch_manager.has_buffered_question():
            self.log_viewer.append_log("No buffered question available, waiting for generation...", "info")
            self.question_panel.show_generating_message()
            self.question_panel.show_previous_qa(ctx.qa_pairs)
            # Transition to QUESTION_GENERATION so on_prefetch_question_ready will show it
            self.state_machine.transition_to(Phase.QUESTION_GENERATION, SubPhase.GENERATING_SINGLE_QUESTION)
            return

        # Get next question from buffer
        question_data = self.question_prefetch_manager.get_next_question()
        if not question_data:
            return

        # Ensure buffer is being refilled after taking a question
        self.question_prefetch_manager.ensure_generating()

        question_text = (question_data.get("question") or "").strip()
        options = question_data.get("options", [])

        if not question_text:
            self.log_viewer.append_log("Received empty question text from buffer", "error")
            self._finish_question_phase()
            return

        # Check if this is the last question
        is_last = ctx.current_question_num + 1 >= ctx.max_questions

        self.state_machine.update_context(
            current_question_text=question_text,
            current_question_options=options,
            is_last_question_shown=is_last
        )

        self.question_panel.show_question(
            question_text,
            options,
            ctx.current_question_num + 1,
            ctx.max_questions,
            is_last=is_last
        )
        self.question_panel.show_previous_qa(ctx.qa_pairs)
        self.question_panel.set_readonly(False)
        self.state_machine.transition_to(Phase.AWAITING_ANSWERS, SubPhase.AWAITING_SINGLE_ANSWER)
        self.log_viewer.append_log(
            f"Showing question {ctx.current_question_num + 1}/{ctx.max_questions}" +
            (" (last question)" if is_last else ""),
            "success"
        )

    @Slot(dict)
    def on_prefetch_question_ready(self, question_data: dict):
        """Handle a question ready from the prefetch manager."""
        ctx = self.state_machine.context

        # Only auto-show if we're actively waiting for a question (QUESTION_GENERATION phase)
        # Do NOT auto-show if user is answering a question (AWAITING_ANSWERS phase)
        if self.state_machine.phase == Phase.QUESTION_GENERATION:
            self.log_viewer.append_log("Question ready, showing it now", "debug")
            self._show_next_buffered_question()
        else:
            self.log_viewer.append_log(
                f"Question ready and buffered (phase: {self.state_machine.phase.name})",
                "debug"
            )

    def _restore_question_ui(self):
        """Restore the current question UI from state context."""
        ctx = self.state_machine.context

        # Re-initialize the prefetch manager with current state
        self.question_prefetch_manager.initialize(
            description=ctx.description,
            provider_name=ctx.llm_config.get("question_gen", "claude"),
            working_directory=ctx.working_directory,
            model=ctx.llm_config.get("question_gen_model"),
            max_questions=ctx.max_questions
        )
        # CRITICAL: Restore QA history AFTER initialize to preserve it
        self.question_prefetch_manager.qa_pairs = list(ctx.qa_pairs)
        self.question_prefetch_manager.questions_generated_count = ctx.current_question_num

        if ctx.current_question_text:
            # Restore the current question being shown
            self.question_panel.show_question(
                ctx.current_question_text,
                ctx.current_question_options,
                ctx.current_question_num + 1,
                ctx.max_questions,
                is_last=ctx.is_last_question_shown
            )
            self.question_panel.show_previous_qa(ctx.qa_pairs)
            self.question_panel.set_readonly(False)
            self.state_machine.set_sub_phase(SubPhase.AWAITING_SINGLE_ANSWER)

            # Resume prefetching in background
            self.question_prefetch_manager.start_prefetching()
        else:
            # No current question text - we were in generation phase when paused
            # Just start prefetching, don't re-initialize (would lose qa_pairs)
            self.log_viewer.append_log("Resuming question generation from saved state...", "info")
            self.state_machine.transition_to(Phase.QUESTION_GENERATION, SubPhase.GENERATING_SINGLE_QUESTION)
            self.question_prefetch_manager.start_prefetching()
            self.question_panel.show_generating_message()
            self.question_panel.show_previous_qa(ctx.qa_pairs)

    def _finish_question_phase(self):
        """Finalize question loop and move to task planning."""
        ctx = self.state_machine.context
        answers = {
            f"q{i + 1}": qa.get("answer", "")
            for i, qa in enumerate(ctx.qa_pairs)
        }
        self.state_machine.update_context(
            answers=answers,
            current_question_text="",
            current_question_options=[]
        )
        self.question_panel.set_readonly(True)
        self.log_viewer.append_log(
            f"Collected {len(ctx.qa_pairs)} question answers, moving to task planning...",
            "info"
        )
        self.state_machine.transition_to(Phase.TASK_PLANNING)
        self.run_task_planning()

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
            self.state_machine.transition_to(Phase.COMPLETED)
            return

        worker = ExecutionWorker(
            provider_name=ctx.llm_config.get("coder", "claude"),
            working_directory=ctx.working_directory,
            current_iteration=ctx.current_iteration,
            model=ctx.llm_config.get("coder_model")
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

    @Slot(object)
    def on_single_task_complete(self, result: dict):
        """Handle single task execution completion - then proceed to review and git."""
        self.log_viewer.append_log(f"Single task execution result: {result}", "debug")

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
            self.state_machine.transition_to(Phase.COMPLETED)
            return

        # Task was worked on - now run review loop for this task's changes
        self.log_viewer.append_log(f"Task iteration {result.get('iteration')} complete", "success")

        # Check if we should run review loop
        if self.state_machine.context.debug_iterations > 0 and self.state_machine.context.review_types:
            self.log_viewer.append_log(f"Running Debug/Review for this task ({self.state_machine.context.debug_iterations} iterations)...", "info")
            self.state_machine.transition_to(Phase.DEBUG_REVIEW)
            self.run_review_loop()
        else:
            # Skip review, go directly to git for this task
            if self.state_machine.context.debug_iterations == 0:
                reason = "0 iterations configured"
            else:
                reason = "no review types selected"
            self.log_viewer.append_log(f"Skipping Debug/Review phase ({reason})", "info")
            self.log_viewer.append_log("Transitioning to Git Operations for this task...", "info")
            self.state_machine.transition_to(Phase.GIT_OPERATIONS)
            self.run_git_operations()

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
            reviewer_model=ctx.llm_config.get("reviewer_model"),
            fixer_model=ctx.llm_config.get("fixer_model")
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
        review_label = review_type.replace('_', ' ').title()
        self.status_panel.set_sub_status(f"Completed: {review_label}")

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
        auto_push = ctx.auto_push
        self.log_viewer.append_log(f"Initial auto_push setting: {auto_push}", "debug")

        # If not auto-push and we remember choice, use that
        if not auto_push and self.remember_push_choice:
            auto_push = self.auto_push_remembered
            self.log_viewer.append_log(f"Using remembered push choice: {auto_push}", "debug")

        # If still not auto-push, ask user
        if not auto_push and not self.remember_push_choice:
            self.log_viewer.append_log("Prompting user for push approval...", "info")
            should_push, remember = GitApprovalDialog.get_approval(self)
            if remember:
                self.remember_push_choice = True
                self.auto_push_remembered = should_push
            auto_push = should_push
            self.log_viewer.append_log(f"User chose: push={should_push}, remember={remember}", "info")

        self.log_viewer.append_log(f"Final push decision: {auto_push}", "info")

        worker = GitWorker(
            provider_name=ctx.llm_config.get("git_ops", "claude"),
            working_directory=ctx.working_directory,
            auto_push=auto_push,
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

        if result.get("committed"):
            self.log_viewer.append_success("Changes committed to local repository")
        else:
            self.log_viewer.append_warning("No commit was made")

        if result.get("pushed"):
            self.log_viewer.append_success("Changes pushed to remote repository")
        else:
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

    @Slot()
    def on_save_settings(self):
        """Handle save settings action."""
        # Get current settings from UI
        llm_config = self.llm_selector_panel.get_config()
        exec_config = self.config_panel.get_config()

        # Create ProjectSettings object
        settings = ProjectSettings(
            question_gen=llm_config.question_gen,
            task_planning=llm_config.task_planning,
            coder=llm_config.coder,
            reviewer=llm_config.reviewer,
            fixer=llm_config.fixer,
            git_ops=llm_config.git_ops,
            question_gen_model=llm_config.question_gen_model,
            task_planning_model=llm_config.task_planning_model,
            coder_model=llm_config.coder_model,
            reviewer_model=llm_config.reviewer_model,
            fixer_model=llm_config.fixer_model,
            git_ops_model=llm_config.git_ops_model,
            max_main_iterations=exec_config.max_main_iterations,
            debug_loop_iterations=exec_config.debug_loop_iterations,
            max_questions=exec_config.max_questions,
            auto_push=exec_config.auto_push,
            working_directory=exec_config.working_directory,
            git_remote=exec_config.git_remote,
            review_types=exec_config.review_types
        )

        # Open file dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project Settings",
            "",
            "JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            try:
                ProjectSettingsManager.save_to_file(settings, file_path)
                self.log_viewer.append_log(f"Settings saved to: {file_path}", "success")
                QMessageBox.information(self, "Success", "Settings saved successfully!")
            except Exception as e:
                self.log_viewer.append_log(f"Failed to save settings: {e}", "error")
                QMessageBox.critical(self, "Error", f"Failed to save settings:\n{e}")

    @Slot()
    def on_load_settings(self):
        """Handle load settings action."""
        # Open file dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Project Settings",
            "",
            "JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            try:
                settings = ProjectSettingsManager.load_from_file(file_path)

                # Apply settings to UI
                llm_config_dict = {
                    "question_gen": settings.question_gen,
                    "task_planning": settings.task_planning,
                    "coder": settings.coder,
                    "reviewer": settings.reviewer,
                    "fixer": settings.fixer,
                    "git_ops": settings.git_ops,
                    "question_gen_model": settings.question_gen_model,
                    "task_planning_model": settings.task_planning_model,
                    "coder_model": settings.coder_model,
                    "reviewer_model": settings.reviewer_model,
                    "fixer_model": settings.fixer_model,
                    "git_ops_model": settings.git_ops_model,
                }
                self.llm_selector_panel.set_config(llm_config_dict)

                exec_config = ExecutionConfig(
                    max_main_iterations=settings.max_main_iterations,
                    debug_loop_iterations=settings.debug_loop_iterations,
                    max_questions=settings.max_questions,
                    auto_push=settings.auto_push,
                    working_directory=settings.working_directory,
                    git_remote=settings.git_remote,
                    review_types=settings.review_types
                )
                self.config_panel.set_config(exec_config)

                self.log_viewer.append_log(f"Settings loaded from: {file_path}", "success")
                QMessageBox.information(self, "Success", "Settings loaded successfully!")
            except Exception as e:
                self.log_viewer.append_log(f"Failed to load settings: {e}", "error")
                QMessageBox.critical(self, "Error", f"Failed to load settings:\n{e}")

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
