"""Main application window."""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QPushButton, QMessageBox, QApplication, QInputDialog
)
from PySide6.QtCore import Qt, Slot, QThreadPool, Signal
from PySide6.QtGui import QAction, QActionGroup
from pathlib import Path
import threading

from .widgets.description_panel import DescriptionPanel
from .widgets.question_panel import QuestionPanel
from .widgets.llm_selector_panel import LLMSelectorPanel
from .widgets.config_panel import ConfigPanel, ExecutionConfig
from .widgets.log_viewer import LogViewer
from .widgets.status_panel import StatusPanel
from .settings_mixin import SettingsMixin
from .workflow_runner import WorkflowRunnerMixin
from ..core.state_machine import StateMachine, Phase, SubPhase
from ..core.debug_settings import DEBUG_STAGE_LABELS, default_debug_breakpoints
from ..core.file_manager import FileManager
from ..core.session_manager import SessionManager
from ..llm.prompt_templates import PromptTemplates

from ..workers.question_worker import QuestionWorker, DefinitionRewriteWorker
from ..workers.llm_worker import LLMWorker
# Import llm module to register providers
from .. import llm


class MainWindow(QMainWindow, WorkflowRunnerMixin, SettingsMixin):
    """
    Primary application window containing all panels and orchestrating
    the interaction between UI components and worker threads.
    """

    debug_step_requested = Signal(str, str)  # (stage key, before|after)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AgentHarness - Autonomous Code Generator")
        self.setMinimumSize(1200, 800)

        self.thread_pool = QThreadPool()
        self.state_machine = StateMachine()
        self.file_manager = None  # Created when working dir is set
        self.session_manager = SessionManager()
        self.current_worker = None
        self.git_mode = "local"
        self.activity_state = {
            "phase": "",
            "action": "",
            "agent": "",
            "review": "",
            "findings": "",
        }
        self._last_phase = None
        self._suppress_description_sync = False
        self.debug_mode_enabled = False
        self.debug_breakpoints = default_debug_breakpoints()
        self.show_llm_terminals = True
        self._debug_wait_event = threading.Event()
        self._debug_wait_event.set()
        self._debug_waiting = False

        LLMWorker.set_debug_gate_callback(self._wait_for_debug_step)
        LLMWorker.set_show_live_terminal_windows(self.show_llm_terminals)

        self.setup_menu_bar()
        self.setup_ui()
        self.connect_signals()
        self._initialize_startup_working_directory()
        self.update_button_states()

    def setup_menu_bar(self):
        """Initialize the menu bar with File menu."""
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        save_action = QAction("&Save Settings...", self)
        save_action.setShortcut("Ctrl+S")
        save_action.setStatusTip("Save current project settings to file")
        save_action.triggered.connect(self.on_save_settings)
        file_menu.addAction(save_action)

        load_action = QAction("&Load Settings...", self)
        load_action.setShortcut("Ctrl+O")
        load_action.setStatusTip("Load project settings from file")
        load_action.triggered.connect(self.on_load_settings)
        file_menu.addAction(load_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("Exit the application")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

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

        settings_menu = menu_bar.addMenu("&Settings")
        self.review_settings_action = QAction("&Review Settings...", self)
        settings_menu.addAction(self.review_settings_action)
        self.debug_settings_action = QAction("&Debug Settings...", self)
        settings_menu.addAction(self.debug_settings_action)

    def setup_ui(self):
        """Initialize and layout all UI components."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        self.status_panel = StatusPanel()
        main_layout.addWidget(self.status_panel)
        main_splitter = QSplitter(Qt.Horizontal)
        self.log_viewer = LogViewer()
        main_splitter.addWidget(self.log_viewer)
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

        self.next_step_button = QPushButton("Next Step")
        self.next_step_button.setMinimumWidth(120)
        self.next_step_button.clicked.connect(self.on_next_step_clicked)
        self.next_step_button.setEnabled(False)
        button_layout.addWidget(self.next_step_button)

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
        self.config_panel.config_changed.connect(self.on_runtime_config_changed)
        self.llm_selector_panel.config_changed.connect(self.on_runtime_llm_config_changed)
        self.review_settings_action.triggered.connect(self.config_panel.open_review_settings)
        self.debug_settings_action.triggered.connect(self.on_open_debug_settings)
        self.debug_step_requested.connect(self.on_debug_step_requested)

    def _initialize_startup_working_directory(self):
        """Initialize artifacts for the startup/default working directory."""
        self._prepare_working_directory(self.config_panel.get_working_directory())

    def _prepare_working_directory(self, path: str):
        """Ensure working-directory artifacts exist and are ready."""
        if not path:
            return
        path_obj = Path(path)
        if not path_obj.exists() or not path_obj.is_dir():
            return

        self.session_manager.set_working_directory(path)
        self.file_manager = FileManager(path)
        try:
            self.file_manager.ensure_files_exist()
            review_files = [
                PromptTemplates.get_review_filename(review_type)
                for review_type in PromptTemplates.get_all_review_types()
            ]
            self.file_manager.ensure_review_files_exist(review_files)
        except Exception as exc:
            self.log_viewer.append_log(f"Failed to initialize working directory files: {exc}", "warning")

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
        self.next_step_button.setEnabled(self._debug_waiting)

        # Also update panel states
        ctx = self.state_machine.context
        description_editable = is_idle or (is_awaiting and ctx.questions_answered and self.current_worker is None)
        self.description_panel.set_readonly(not description_editable)
        self.llm_selector_panel.set_enabled(True)
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
    def on_next_step_clicked(self):
        """Continue execution after a debug breakpoint."""
        if not self._debug_waiting:
            return
        self._debug_wait_event.set()
        self._set_debug_waiting(False)

    @Slot(str, str)
    def on_debug_step_requested(self, stage: str, when: str):
        """Update UI when an LLM debug breakpoint is reached."""
        stage_label = DEBUG_STAGE_LABELS.get(stage, stage.replace("_", " ").title())
        when_label = "before" if when == "before" else "after"
        self._set_debug_waiting(True)
        self.log_viewer.append_log(
            f"Debug breakpoint hit ({when_label} {stage_label}). Click Next Step to continue.",
            "warning"
        )

    def _set_debug_waiting(self, waiting: bool):
        """Toggle waiting state for debug step mode controls."""
        self._debug_waiting = waiting
        self.next_step_button.setEnabled(waiting)

    def _release_debug_wait(self):
        """Release any blocked debug wait to avoid deadlock on pause/stop."""
        self._debug_wait_event.set()
        self._set_debug_waiting(False)

    def _wait_for_debug_step(self, stage: str, when: str) -> bool:
        """Block worker thread until user clicks Next Step for configured breakpoints."""
        if not self._should_wait_for_debug_step(stage, when):
            return True
        self._debug_wait_event.clear()
        self.debug_step_requested.emit(stage, when)
        while not self._debug_wait_event.wait(timeout=0.1):
            if self.current_worker and self.current_worker.is_cancelled():
                return False
            if self.state_machine.context.pause_requested:
                return False
        return True

    def _should_wait_for_debug_step(self, stage: str, when: str) -> bool:
        """Return True when debug mode should pause at this stage boundary."""
        if not self.debug_mode_enabled:
            return False
        stage_config = self.debug_breakpoints.get(stage, {})
        return bool(stage_config.get(when, False))

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
        self._release_debug_wait()
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
            debug_mode_enabled=self.debug_mode_enabled,
            debug_breakpoints=self.debug_breakpoints,
            show_llm_terminals=self.show_llm_terminals,
            max_questions=config.max_questions,
            tasks_per_iteration=config.tasks_per_iteration,
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
            run_unit_test_prep=config.run_unit_test_prep,
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
        self.log_viewer.append_log(f"  Tasks Per Iteration: {config.tasks_per_iteration}", "info")
        self.log_viewer.append_log(f"  Number of Questions: {config.max_questions}", "info")
        self.log_viewer.append_log(f"  Debug Loop Iterations: {config.debug_loop_iterations}", "info")
        self.log_viewer.append_log(f"  Debug Step Mode: {'enabled' if self.debug_mode_enabled else 'disabled'}", "info")
        self.log_viewer.append_log(
            f"  LLM Terminal Windows: {'shown' if self.show_llm_terminals else 'hidden'}",
            "info"
        )
        review_types = config.review_types or []
        review_labels = ", ".join(
            [PromptTemplates.get_review_display_name(r) for r in review_types]
        ) or "(none)"
        self.log_viewer.append_log(f"  Review Types: {review_labels}", "info")
        self.log_viewer.append_log(
            f"  Pre-Review Unit Test Update: {'enabled' if config.run_unit_test_prep else 'disabled'}",
            "info"
        )
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
        self._release_debug_wait()

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
            self._release_debug_wait()

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
        self._release_debug_wait()
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
        if not path:
            return
        path_obj = Path(path)
        if not path_obj.exists() or not path_obj.is_dir():
            return

        self._prepare_working_directory(path)
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
                max_questions=ctx.max_questions,
                review_types=ctx.review_types,
                run_unit_test_prep=ctx.run_unit_test_prep,
                tasks_per_iteration=ctx.tasks_per_iteration
            ))
            self._apply_git_mode(ctx.git_mode)

            self.file_manager = FileManager(ctx.working_directory)
            self._sync_description_to_file(ctx.description)
            self.debug_mode_enabled = ctx.debug_mode_enabled
            self.debug_breakpoints = ctx.debug_breakpoints
            self.show_llm_terminals = ctx.show_llm_terminals
            LLMWorker.set_show_live_terminal_windows(self.show_llm_terminals)

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

    @Slot()
    def on_runtime_config_changed(self):
        """Apply live config edits to the current run context."""
        config = self.config_panel.get_config()
        self.state_machine.update_context(
            max_iterations=config.max_main_iterations,
            debug_iterations=config.debug_loop_iterations,
            max_questions=config.max_questions,
            tasks_per_iteration=config.tasks_per_iteration,
            git_mode=config.git_mode,
            git_remote=config.git_remote,
            review_types=config.review_types,
            run_unit_test_prep=config.run_unit_test_prep
        )
        if self._should_show_activity(self.state_machine.phase):
            self.activity_state["agent"] = self._get_agent_label(self.state_machine.phase)
            self._refresh_activity_panel()

    @Slot()
    def on_runtime_llm_config_changed(self):
        """Apply live LLM selection edits to the current run context."""
        self.state_machine.update_context(llm_config=self.llm_selector_panel.get_config_dict())
        if self._should_show_activity(self.state_machine.phase):
            self.activity_state["agent"] = self._get_agent_label(self.state_machine.phase)
            self._refresh_activity_panel()

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
        if not self.config_panel.ensure_git_ready(ctx.working_directory, self.config_panel.get_git_remote()):
            self.log_viewer.append_log(
                "Cannot start task planning because git repository initialization failed.",
                "error"
            )
            QMessageBox.warning(
                self,
                "Git Initialization Required",
                "Task planning requires a git repository in the working directory.\n"
                "Please install/fix Git and try again."
            )
            return
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
