"""Main application window."""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QPushButton, QMessageBox, QApplication, QFileDialog, QInputDialog
)
from PySide6.QtCore import Qt, Slot, QThreadPool
from PySide6.QtGui import QAction, QActionGroup
from pathlib import Path

from .widgets.description_panel import DescriptionPanel
from .widgets.question_panel import QuestionPanel
from .widgets.llm_selector_panel import LLMSelectorPanel
from .widgets.config_panel import ConfigPanel, ExecutionConfig
from .widgets.log_viewer import LogViewer
from .widgets.status_panel import StatusPanel
from .workflow_runner import WorkflowRunnerMixin
from ..core.state_machine import StateMachine, Phase, SubPhase
from ..core.file_manager import FileManager
from ..core.session_manager import SessionManager
from ..core.project_settings import ProjectSettings, ProjectSettingsManager
from ..llm.prompt_templates import PromptTemplates

from ..workers.question_worker import QuestionWorker, DefinitionRewriteWorker
# Import llm module to register providers
from .. import llm


class MainWindow(QMainWindow, WorkflowRunnerMixin):
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

        # Git mode preference
        self.git_mode = "local"

        # Activity panel state
        self.activity_state = {
            "phase": "",
            "action": "",
            "agent": "",
            "review": "",
            "findings": "",
        }
        self._last_phase = None
        self._suppress_description_sync = False

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

        # Git menu
        git_menu = menu_bar.addMenu("&Git")
        self.git_mode_group = QActionGroup(self)
        self.git_mode_group.setExclusive(True)
        self.git_mode_actions = {}

        def add_git_action(label: str, mode: str):
            action = QAction(label, self, checkable=True)
            action.triggered.connect(lambda _checked=False, m=mode: self.set_git_mode(m))
            self.git_mode_group.addAction(action)
            git_menu.addAction(action)
            self.git_mode_actions[mode] = action

        add_git_action("No Git Actions", "off")
        add_git_action("Local Commit Only", "local")
        add_git_action("Remote + Push", "push")

        self.git_mode_actions[self.git_mode].setChecked(True)

        # Settings menu
        settings_menu = menu_bar.addMenu("&Settings")
        self.review_settings_action = QAction("&Review Settings...", self)
        settings_menu.addAction(self.review_settings_action)

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
        self.config_panel.set_git_mode(self.git_mode)
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
        self.question_panel.generate_again_requested.connect(self.on_generate_again_requested)
        self.question_panel.start_planning_requested.connect(self.on_start_planning_requested)

        # Description panel
        self.description_panel.description_changed.connect(self.on_description_changed)

        # Config panel
        self.config_panel.working_directory_changed.connect(self.on_working_dir_changed)
        self.review_settings_action.triggered.connect(self.config_panel.open_review_settings)

    def set_git_mode(self, mode: str):
        """Set git mode and update related UI."""
        if mode == self.git_mode:
            return

        previous = self.git_mode
        if mode == "push":
            current_remote = self.config_panel.get_git_remote()
            remote, ok = QInputDialog.getText(
                self,
                "Git Remote",
                "Enter Git remote URL:",
                text=current_remote
            )
            if not ok:
                self._apply_git_mode(previous)
                return
            remote = remote.strip()
            if not remote:
                QMessageBox.warning(
                    self,
                    "Missing Git Remote",
                    "Remote + Push requires a Git remote URL."
                )
                self._apply_git_mode(previous)
                return
            self.config_panel.set_git_remote(remote)

        self._apply_git_mode(mode)

    def _apply_git_mode(self, mode: str):
        """Apply git mode without prompting."""
        self.git_mode = mode
        if hasattr(self, "git_mode_actions") and mode in self.git_mode_actions:
            self.git_mode_actions[mode].setChecked(True)
        if hasattr(self, "config_panel"):
            self.config_panel.set_git_mode(mode)

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
        ctx = self.state_machine.context
        description_editable = is_idle or (is_awaiting and ctx.questions_answered and self.current_worker is None)
        self.description_panel.set_readonly(not description_editable)
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
        if (phase == Phase.
                MAIN_EXECUTION):
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

        if self.git_mode == "push" and not self.config_panel.get_config().git_remote:
            QMessageBox.warning(
                self,
                "Missing Git Remote",
                "Git mode is set to 'Remote + Push'. Please enter a Git remote URL."
            )
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
            questions_json={},
            questions_answered=False,
            answers={},
            git_mode=self.git_mode,
            git_remote=config.git_remote,
            review_types=config.review_types,
            llm_config=llm_config
        )
        self._reset_activity_state()

        # Initialize file manager
        self.file_manager = FileManager(working_dir)
        self.session_manager.set_working_directory(working_dir)
        self._sync_description_to_file(self.description_panel.get_description())

        # Clear log
        self.log_viewer.clear()
        self.log_viewer.append_log("Starting workflow...", "info")
        self.log_viewer.append_log("=" * 50, "info")
        self.log_viewer.append_log("WORKFLOW CONFIGURATION:", "info")
        self.log_viewer.append_log(f"  Working Directory: {working_dir}", "info")
        self.log_viewer.append_log(f"  Max Main Iterations: {config.max_main_iterations}", "info")
        self.log_viewer.append_log(f"  Number of Questions: {config.max_questions}", "info")
        self.log_viewer.append_log(f"  Debug Loop Iterations: {config.debug_loop_iterations}", "info")
        review_types = config.review_types or []
        review_labels = ", ".join(
            [PromptTemplates.get_review_display_name(r) for r in review_types]
        ) or "(none)"
        self.log_viewer.append_log(f"  Review Types: {review_labels}", "info")
        self.log_viewer.append_log(f"  Git Mode: {self.git_mode}", "info")
        self.log_viewer.append_log(f"  Git Remote: {config.git_remote or '(not set)'}", "info")
        self.log_viewer.append_log("LLM PROVIDERS:", "info")
        self.log_viewer.append_log(f"  Question Gen: {llm_config.get('question_gen', 'N/A')}", "info")
        self.log_viewer.append_log(f"  Description Molding: {llm_config.get('description_molding', 'N/A')}", "info")
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
                self.log_viewer.append_log("User cancelled start after question count warning.", "info")
                return

            self.log_viewer.append_log("Number of questions set to 0 - skipping question phase.", "warning")
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

        review_name = PromptTemplates.get_review_display_name(review_type)
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
            self.file_manager = FileManager(path)
            existing = self._load_description_from_file()
            if existing:
                self.description_panel.set_description(existing)
                self.state_machine.update_context(description=existing)
            else:
                self._sync_description_to_file(self.description_panel.get_description())

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
                working_directory=ctx.working_directory,
                git_remote=ctx.git_remote,
                git_mode=ctx.git_mode,
                max_questions=ctx.max_questions
            ))
            self._apply_git_mode(ctx.git_mode)

            self.file_manager = FileManager(ctx.working_directory)
            self._sync_description_to_file(ctx.description)

            self.log_viewer.append_log("Session restored", "success")
            if self.state_machine.phase == Phase.AWAITING_ANSWERS:
                self._restore_question_ui()
            self.update_button_states()

        except Exception as e:
            self.log_viewer.append_error(f"Failed to load session: {e}")

    @Slot(list)
    def on_answers_submitted(self, qa_pairs: list):
        """Handle submission of a batch of question answers."""
        updated_pairs = []

        for qa in qa_pairs:
            question = str(qa.get("question", "")).strip()
            answer = str(qa.get("answer", "")).strip()
            if question and answer:
                updated_pairs.append({"question": question, "answer": answer})

        answers = {
            f"q{i + 1}": qa.get("answer", "")
            for i, qa in enumerate(updated_pairs)
        }

        description = self.description_panel.get_description()
        self.state_machine.update_context(
            qa_pairs=updated_pairs,
            answers=answers,
            questions_answered=True,
            description=description
        )
        self.question_panel.show_updating_description()
        self.log_viewer.append_log("Saved answers; updating project description...", "info")
        self.run_definition_rewrite()

    @Slot()
    def on_generate_again_requested(self):
        """Handle user request to generate another batch of questions."""
        ctx = self.state_machine.context
        if self.current_worker:
            self.log_viewer.append_log("Please wait for the description update to finish.", "info")
            return
        if not ctx.questions_answered:
            answered_pairs = self.question_panel.collect_answered_pairs()
            if answered_pairs and self.question_panel.get_unanswered_count() == 0:
                updated_pairs = list(answered_pairs)
                answers = {
                    f"q{i + 1}": qa.get("answer", "")
                    for i, qa in enumerate(updated_pairs)
                }
                self.state_machine.update_context(
                    qa_pairs=updated_pairs,
                    answers=answers,
                    questions_answered=True,
                    description=self.description_panel.get_description()
                )
        self.log_viewer.append_log(
            f"Generating another batch of {ctx.max_questions} questions...",
            "info"
        )
        if ctx.working_directory:
            questions_path = Path(ctx.working_directory) / "questions.json"
            if questions_path.exists():
                try:
                    questions_path.unlink()
                    self.log_viewer.append_log("Deleted previous questions.json", "info")
                except OSError as exc:
                    self.log_viewer.append_log(
                        f"Failed to delete questions.json: {exc}",
                        "warning"
                    )
        self.state_machine.update_context(
            questions_json={},
            questions_answered=False
        )
        self.question_panel.set_readonly(True)
        self.question_panel.show_generating_message()
        self.run_question_generation()

    @Slot()
    def on_start_planning_requested(self):
        """Handle user request to start planning."""
        self.log_viewer.append_log("User requested to start planning", "info")
        self._finish_question_phase()

    # =========================================================================
    # Worker execution methods
    # =========================================================================

    def run_question_generation(self):
        """Run Phase 1: Question Generation (batch)."""
        ctx = self.state_machine.context
        description = self.description_panel.get_description()
        self._sync_description_to_file(description)
        if description != ctx.description:
            self.state_machine.update_context(description=description)
        if ctx.working_directory:
            questions_path = Path(ctx.working_directory) / "questions.json"
            try:
                questions_path.write_text("", encoding="utf-8")
                self.log_viewer.append_log("Initialized empty questions.json", "info")
            except OSError as exc:
                self.log_viewer.append_log(
                    f"Failed to initialize questions.json: {exc}",
                    "warning"
                )

        worker = QuestionWorker(
            description=description,
            question_count=ctx.max_questions,
            previous_qa=[],
            provider_name=ctx.llm_config.get("question_gen", "claude"),
            working_directory=ctx.working_directory,
            model=ctx.llm_config.get("question_gen_model")
        )

        self._connect_worker_signals(worker)
        worker.signals.questions_ready.connect(self.on_questions_ready)

        self.current_worker = worker
        self.thread_pool.start(worker)

        self.log_viewer.append_log("Generating question batch...", "info")
        self.question_panel.show_generating_message()
        self.state_machine.transition_to(Phase.QUESTION_GENERATION, SubPhase.GENERATING_QUESTIONS)

    def run_definition_rewrite(self):
        """Rewrite the description from Q&A before generating more questions."""
        ctx = self.state_machine.context
        if not ctx.qa_pairs:
            self.run_question_generation()
            return

        worker = DefinitionRewriteWorker(
            description=self.description_panel.get_description(),
            qa_pairs=ctx.qa_pairs,
            provider_name=ctx.llm_config.get("description_molding", "gemini"),
            working_directory=ctx.working_directory,
            model=ctx.llm_config.get("description_molding_model", "gemini-3-pro-preview")
        )

        self._connect_worker_signals(worker)
        worker.signals.result.connect(self.on_definition_rewrite_ready)

        self.current_worker = worker
        self.thread_pool.start(worker)

    @Slot(str)
    def on_definition_rewrite_ready(self, definition: str):
        """Handle completion of the product definition rewrite."""
        updated = self._load_rewritten_description_from_file() or (definition or "").strip()
        if updated:
            self._suppress_description_sync = True
            try:
                self.description_panel.set_description(updated)
            finally:
                self._suppress_description_sync = False
            self.state_machine.update_context(
                description=updated,
                qa_pairs=[],
                answers={}
            )
            self._sync_description_to_file(updated)
            self.log_viewer.append_log("Updated product description from Q&A rewrite", "success")
        else:
            self.log_viewer.append_log(
                "Definition rewrite returned empty output; using existing description",
                "warning"
            )
        self.question_panel.show_answers_saved()

    @Slot(str)
    def on_description_changed(self, text: str):
        """Keep product-description.md synced with UI edits."""
        if self._suppress_description_sync:
            return
        self.state_machine.update_context(description=text)
        self._sync_description_to_file(text)

    def _sync_description_to_file(self, text: str):
        """Persist the current description to product-description.md."""
        if not self.file_manager:
            return
        try:
            self.file_manager.ensure_files_exist()
            self.file_manager.write_file("product-description.md", text.strip() + "\n" if text else "")
        except Exception as exc:
            self.log_viewer.append_log(f"Failed to write product-description.md: {exc}", "warning")

    def _load_description_from_file(self) -> str:
        """Load product-description.md content when available."""
        if not self.file_manager:
            return ""
        try:
            content = self.file_manager.read_file("product-description.md")
        except Exception as exc:
            self.log_viewer.append_log(f"Failed to read product-description.md: {exc}", "warning")
            return ""
        return (content or "").strip()

    def _load_rewritten_description_from_file(self) -> str:
        """Load product-description.md after Q&A rewrite."""
        ctx = self.state_machine.context
        if not ctx.working_directory:
            return ""
        path = Path(ctx.working_directory) / "product-description.md"
        if not path.exists():
            return ""
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            self.log_viewer.append_log(f"Failed to read product-description.md: {exc}", "warning")
            return ""
        return (content or "").strip()

    @Slot(dict)
    def on_questions_ready(self, questions: dict):
        """Handle batch question generation."""
        ctx = self.state_machine.context
        question_list = questions.get("questions", [])

        self.state_machine.update_context(
            questions_json=questions,
            questions_answered=False
        )

        self.question_panel.show_questions(question_list)
        self.question_panel.set_readonly(False)
        self.state_machine.transition_to(Phase.AWAITING_ANSWERS, SubPhase.AWAITING_ANSWERS)
        self.log_viewer.append_log(f"Loaded {len(question_list)} questions for answering", "success")

    def _restore_question_ui(self):
        """Restore the current question UI from state context."""
        ctx = self.state_machine.context
        question_list = []
        if isinstance(ctx.questions_json, dict):
            question_list = ctx.questions_json.get("questions", [])

        if question_list:
            self.question_panel.show_questions(question_list)
            if ctx.questions_answered:
                self.question_panel.show_answers_saved()
            else:
                self.question_panel.set_readonly(False)
            self.state_machine.set_sub_phase(SubPhase.AWAITING_ANSWERS)
            return

        self.log_viewer.append_log("Resuming question generation from saved state...", "info")
        self.question_panel.show_generating_message()
        self.run_question_generation()

    def _finish_question_phase(self):
        """Finalize question loop and move to task planning."""
        ctx = self.state_machine.context
        description = self.description_panel.get_description()
        self._sync_description_to_file(description)
        answers = {
            f"q{i + 1}": qa.get("answer", "")
            for i, qa in enumerate(ctx.qa_pairs)
        }
        self.state_machine.update_context(
            answers=answers,
            current_question_text="",
            current_question_options=[],
            questions_json={},
            questions_answered=True,
            description=description
        )
        self.question_panel.set_readonly(True)
        self.log_viewer.append_log(
            f"Collected {len(ctx.qa_pairs)} question answers, moving to task planning...",
            "info"
        )
        self.state_machine.transition_to(Phase.TASK_PLANNING)
        self.run_task_planning()

    @Slot()
    def on_save_settings(self):
        """Handle save settings action."""
        # Get current settings from UI
        llm_config = self.llm_selector_panel.get_config()
        exec_config = self.config_panel.get_config()

        # Create ProjectSettings object
        settings = ProjectSettings(
            question_gen=llm_config.question_gen,
            description_molding=llm_config.description_molding,
            task_planning=llm_config.task_planning,
            coder=llm_config.coder,
            reviewer=llm_config.reviewer,
            fixer=llm_config.fixer,
            git_ops=llm_config.git_ops,
            question_gen_model=llm_config.question_gen_model,
            description_molding_model=llm_config.description_molding_model,
            task_planning_model=llm_config.task_planning_model,
            coder_model=llm_config.coder_model,
            reviewer_model=llm_config.reviewer_model,
            fixer_model=llm_config.fixer_model,
            git_ops_model=llm_config.git_ops_model,
            max_main_iterations=exec_config.max_main_iterations,
            debug_loop_iterations=exec_config.debug_loop_iterations,
            max_questions=exec_config.max_questions,
            git_mode=exec_config.git_mode,
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
                    "description_molding": settings.description_molding,
                    "task_planning": settings.task_planning,
                    "coder": settings.coder,
                    "reviewer": settings.reviewer,
                    "fixer": settings.fixer,
                    "git_ops": settings.git_ops,
                    "question_gen_model": settings.question_gen_model,
                    "description_molding_model": settings.description_molding_model,
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
                    working_directory=settings.working_directory,
                    git_remote=settings.git_remote,
                    git_mode=settings.git_mode,
                    review_types=settings.review_types
                )
                self.config_panel.set_config(exec_config)
                self._apply_git_mode(settings.git_mode)

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
