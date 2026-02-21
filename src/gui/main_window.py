"""Main application window."""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QPushButton, QMessageBox, QApplication, QInputDialog,
    QStyle, QTabWidget, QDialog, QFormLayout, QDialogButtonBox, QComboBox
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
from .widgets.chat_panel import ChatPanel
from .settings_mixin import SettingsMixin
from .workflow_runner import WorkflowRunnerMixin
from .theme import apply_app_theme, animate_fade_in
from ..core.state_machine import StateMachine, Phase, SubPhase
from ..core.debug_settings import DEBUG_STAGE_LABELS, default_debug_breakpoints
from ..core.file_manager import FileManager
from ..core.session_manager import SessionManager
from ..core.error_context import ErrorRecoveryTracker
from ..core.file_watcher import DescriptionFileWatcher
from ..core.chat_history_manager import ChatHistoryManager
from ..llm.prompt_templates import PromptTemplates
from ..llm.base_provider import LLMProviderRegistry
from ..utils.markdown_parser import has_incomplete_tasks, parse_tasks

from ..workers.question_worker import QuestionWorker, DefinitionRewriteWorker
from ..workers.llm_worker import LLMWorker
# Import llm module to register providers
from .. import llm as llm  # noqa: F401


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
        apply_app_theme(QApplication.instance())

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
        self._resume_incomplete_tasks_directory = ""
        self.debug_mode_enabled = False
        self.debug_breakpoints = default_debug_breakpoints()
        self.show_llm_terminals = True
        self._debug_wait_event = threading.Event()
        self._debug_wait_event.set()
        self._debug_waiting = False
        self.error_recovery_tracker = ErrorRecoveryTracker()
        self._initial_description_message_id = None
        self._last_worker_status = ""
        self._task_progress_cycle_active = False
        self._task_progress_cycle_baseline_completed = 0
        self._suppress_external_description_prompt = False
        self._description_bootstrap_prompted_paths = set()
        self._description_bootstrap_prev_content = ""

        # File watcher for external edits to product-description.md
        self.description_watcher = DescriptionFileWatcher(self)
        self.description_watcher.file_changed_externally.connect(self._on_description_changed_externally)

        # Store description content separately since description_panel is now task-only
        self._description_content = ""

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
        menu_bar.setCornerWidget(self._create_workflow_icon_buttons(), Qt.TopRightCorner)

        file_menu = menu_bar.addMenu("&File")
        self.open_project_action = QAction("&Open Project...", self)
        file_menu.addAction(self.open_project_action)

        file_menu.addSeparator()

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
        self.configuration_settings_action = QAction("&Configuration Settings...", self)
        settings_menu.addAction(self.configuration_settings_action)
        self.llm_settings_action = QAction("&LLM Settings...", self)
        settings_menu.addAction(self.llm_settings_action)
        self.review_settings_action = QAction("&Review Settings...", self)
        settings_menu.addAction(self.review_settings_action)
        self.debug_settings_action = QAction("&Debug Settings...", self)
        settings_menu.addAction(self.debug_settings_action)

        workflow_menu = menu_bar.addMenu("&Workflow")
        self.start_workflow_action = QAction("&Start", self)
        self.start_workflow_action.setShortcut("Ctrl+Return")
        self.start_workflow_action.triggered.connect(self.on_start_clicked)
        workflow_menu.addAction(self.start_workflow_action)

        self.pause_workflow_action = QAction("&Pause", self)
        self.pause_workflow_action.setShortcut("Ctrl+Shift+P")
        self.pause_workflow_action.triggered.connect(self.on_pause_clicked)
        workflow_menu.addAction(self.pause_workflow_action)

        self.stop_workflow_action = QAction("S&top", self)
        self.stop_workflow_action.setShortcut("Ctrl+.")
        self.stop_workflow_action.triggered.connect(self.on_stop_clicked)
        workflow_menu.addAction(self.stop_workflow_action)

        self.next_step_action = QAction("&Next Step", self)
        self.next_step_action.setShortcut("F10")
        self.next_step_action.triggered.connect(self.on_next_step_clicked)
        workflow_menu.addAction(self.next_step_action)

        view_menu = menu_bar.addMenu("&View")

        # Left panel tab toggles
        self.show_logs_action = QAction("Show Logs", self, checkable=True)
        self.show_logs_action.setChecked(False)
        self.show_logs_action.toggled.connect(self.on_toggle_logs)
        view_menu.addAction(self.show_logs_action)

        self.show_description_action = QAction("Show Description", self, checkable=True)
        self.show_description_action.setChecked(False)
        self.show_description_action.toggled.connect(self.on_toggle_description)
        view_menu.addAction(self.show_description_action)

        self.show_tasks_action = QAction("Show Tasks", self, checkable=True)
        self.show_tasks_action.setChecked(False)
        self.show_tasks_action.toggled.connect(self.on_toggle_tasks)
        view_menu.addAction(self.show_tasks_action)

        # Chat panel is always visible (primary input method) - no toggle needed

    def _create_workflow_icon_buttons(self):
        """Create icon buttons for workflow control in the menu bar."""
        # Store as member to prevent premature deletion by Qt
        self.menu_button_container = QWidget()
        layout = QHBoxLayout(self.menu_button_container)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(4)

        # Start button
        self.menu_start_button = QPushButton()
        self.menu_start_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.menu_start_button.setToolTip("Start workflow (Ctrl+Return)")
        self.menu_start_button.setFixedSize(32, 28)
        self.menu_start_button.clicked.connect(self.on_start_clicked)
        self.menu_start_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #2f8fd1, stop:1 #266da9);
                color: white;
                border: 1px solid #57a7dc;
                border-radius: 4px;
                padding: 4px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #3b9ce0, stop:1 #2d78b8);
                border-color: #6eb5e3;
            }
            QPushButton:pressed {
                background: #245f95;
            }
            QPushButton:disabled {
                background: #1d2a36;
                border-color: #2a3e4f;
                color: #7f9bb4;
            }
        """)
        layout.addWidget(self.menu_start_button)

        # Pause button
        self.menu_pause_button = QPushButton()
        self.menu_pause_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        self.menu_pause_button.setToolTip("Pause workflow (Ctrl+Shift+P)")
        self.menu_pause_button.setFixedSize(32, 28)
        self.menu_pause_button.clicked.connect(self.on_pause_clicked)
        self.menu_pause_button.setEnabled(False)
        self.menu_pause_button.setStyleSheet("""
            QPushButton {
                background: #1d2a36;
                color: white;
                border: 1px solid #3a4856;
                border-radius: 4px;
                padding: 4px;
            }
            QPushButton:hover {
                background: #2a3e4f;
                border-color: #4f6377;
            }
            QPushButton:pressed {
                background: #16212b;
            }
            QPushButton:disabled {
                background: #1d2a36;
                border-color: #2a3e4f;
                color: #7f9bb4;
            }
        """)
        layout.addWidget(self.menu_pause_button)

        # Stop button
        self.menu_stop_button = QPushButton()
        self.menu_stop_button.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.menu_stop_button.setToolTip("Stop workflow (Ctrl+.)")
        self.menu_stop_button.setFixedSize(32, 28)
        self.menu_stop_button.clicked.connect(self.on_stop_clicked)
        self.menu_stop_button.setEnabled(False)
        self.menu_stop_button.setStyleSheet("""
            QPushButton {
                background: #c74545;
                color: white;
                border: 1px solid #d86565;
                border-radius: 4px;
                padding: 4px;
            }
            QPushButton:hover {
                background: #d95656;
                border-color: #e87676;
            }
            QPushButton:pressed {
                background: #b03434;
            }
            QPushButton:disabled {
                background: #1d2a36;
                border-color: #2a3e4f;
                color: #7f9bb4;
            }
        """)
        layout.addWidget(self.menu_stop_button)

        # Next Step button
        self.menu_next_step_button = QPushButton()
        self.menu_next_step_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))
        self.menu_next_step_button.setToolTip("Next Step (F10)")
        self.menu_next_step_button.setFixedSize(32, 28)
        self.menu_next_step_button.clicked.connect(self.on_next_step_clicked)
        self.menu_next_step_button.setEnabled(False)
        self.menu_next_step_button.setStyleSheet("""
            QPushButton {
                background: #1d2a36;
                color: white;
                border: 1px solid #3a4856;
                border-radius: 4px;
                padding: 4px;
            }
            QPushButton:hover {
                background: #2a3e4f;
                border-color: #4f6377;
            }
            QPushButton:pressed {
                background: #16212b;
            }
            QPushButton:disabled {
                background: #1d2a36;
                border-color: #2a3e4f;
                color: #7f9bb4;
            }
        """)
        layout.addWidget(self.menu_next_step_button)

        return self.menu_button_container

    def setup_ui(self):
        """Initialize and layout all UI components."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(14, 12, 14, 14)
        main_layout.setSpacing(10)

        self.status_panel = StatusPanel()
        # Status panel is always visible
        main_layout.addWidget(self.status_panel)
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setHandleWidth(4)

        # Left side: Tabbed view for logs, description preview, and task list
        self.left_tab_widget = QTabWidget()

        # Logs tab
        self.log_viewer = LogViewer()
        self.left_tab_widget.addTab(self.log_viewer, "Logs")

        # Description preview tab (read-only markdown preview)
        from PySide6.QtWidgets import QTextBrowser
        self.left_description_preview = QTextBrowser()
        self.left_description_preview.setOpenExternalLinks(True)
        self.left_description_preview.setMinimumHeight(300)
        self.left_tab_widget.addTab(self.left_description_preview, "Description")

        # Task list tab (uses DescriptionPanel in task list mode)
        self.description_panel = DescriptionPanel()
        self.description_panel.set_preview_controls_visible(False)  # Hide mode controls
        self.description_panel._set_mode("task_list")  # Start in task list mode
        self.left_tab_widget.addTab(self.description_panel, "Tasks")

        # Track which tabs are enabled
        self._logs_enabled = False
        self._description_enabled = False
        self._tasks_enabled = False

        # Hide tabs by default - will be shown when at least one is enabled
        self.left_tab_widget.hide()
        main_splitter.addWidget(self.left_tab_widget)

        # Right column: Only chat panel
        right_column = QWidget()
        right_column_layout = QVBoxLayout(right_column)
        right_column_layout.setContentsMargins(0, 0, 0, 0)

        # Chat panel for client messages (always visible - primary input method)
        self.chat_panel = ChatPanel()
        right_column_layout.addWidget(self.chat_panel, stretch=1)

        self.llm_selector_panel = LLMSelectorPanel()
        self.llm_selector_panel.hide()

        self.config_panel = ConfigPanel()
        self.config_panel.set_git_mode(self.git_mode)
        self.config_panel.hide()

        # Bottom section of right column: Clarifying Questions (larger)
        self.question_panel = QuestionPanel()
        self.question_panel.setMinimumHeight(300)

        main_splitter.addWidget(right_column)

        # Set main splitter sizes (40% logs, 60% rest)
        main_splitter.setSizes([480, 720])

        main_layout.addWidget(main_splitter, stretch=1)
        animate_fade_in(self.left_tab_widget, duration_ms=420, delay_ms=100)
        animate_fade_in(right_column, duration_ms=440, delay_ms=160)

        self._set_logs_panel_visible(False)

    def connect_signals(self):
        """Connect UI signals to slots."""
        # State machine signals
        self.state_machine.phase_changed.connect(self.on_phase_changed)
        self.state_machine.workflow_completed.connect(self.on_workflow_completed)

        # Question panel
        self.question_panel.answers_submitted.connect(self.on_answers_submitted)
        self.question_panel.generate_again_requested.connect(self.on_generate_again_requested)
        self.question_panel.start_planning_requested.connect(self.on_start_planning_requested)
        self.question_panel.set_description_callbacks(
            self._get_description,
            self._apply_edited_description
        )

        # Description panel
        # Note: description_changed signal no longer connected - description updates come through chat
        # self.description_panel.description_changed.connect(self.on_description_changed)

        # Config panel
        self.config_panel.working_directory_changed.connect(self.on_working_dir_changed)
        self.config_panel.config_changed.connect(self.on_runtime_config_changed)
        self.llm_selector_panel.config_changed.connect(self.on_runtime_llm_config_changed)
        self.open_project_action.triggered.connect(self.on_open_project_directory)
        self.configuration_settings_action.triggered.connect(self.on_open_configuration_settings)
        self.llm_settings_action.triggered.connect(self.on_open_llm_settings)
        self.review_settings_action.triggered.connect(self.config_panel.open_review_settings)
        self.debug_settings_action.triggered.connect(self.on_open_debug_settings)
        self.debug_step_requested.connect(self.on_debug_step_requested)

        # Status panel
        self.status_panel.resume_incomplete_tasks.connect(self.on_resume_incomplete_tasks_clicked)

        # Chat panel
        self.chat_panel.message_sent.connect(self.on_client_message_sent)
        self.chat_panel.clear_history_requested.connect(self.on_clear_chat_history)
        self.chat_panel.bot_message_added.connect(self.on_bot_message_added)

    def _initialize_startup_working_directory(self):
        """Initialize artifacts for the startup/default working directory."""
        path = self.config_panel.get_working_directory()
        self._prepare_working_directory(path)

        # Start file watcher for product-description.md
        if path:
            self.description_watcher.start_watching(path)

        # Check for incomplete tasks at startup
        if path and self._working_directory_has_incomplete_tasks(path):
            reply = QMessageBox.question(
                self,
                "Incomplete Tasks Found",
                "There are incomplete tasks in this project.\n"
                "Would you like to continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                # Ask for iteration count
                iterations, ok = self._prompt_iteration_count()
                if ok and iterations > 0:
                    self._resume_incomplete_tasks_directory = path
                    # Set max iterations for the resume
                    self.state_machine.update_context(max_iterations=iterations)
                    self.log_viewer.append_log(
                        f"Resuming incomplete tasks with {iterations} iterations...",
                        "info"
                    )
                    # Automatically start the workflow after a short delay to ensure UI is ready
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(100, self.on_start_clicked)
                else:
                    self.log_viewer.append_log("Resume cancelled by user (no iterations specified).", "info")
                    self._resume_incomplete_tasks_directory = ""
            else:
                self.log_viewer.append_log("Resume declined by user.", "info")
                self._resume_incomplete_tasks_directory = ""

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

    def _working_directory_has_incomplete_tasks(self, path: str) -> bool:
        """Return True when tasks.md exists and contains unchecked tasks."""
        if not path:
            return False
        tasks_path = Path(path) / FileManager.TASKS_FILE
        if not tasks_path.exists():
            return False
        try:
            return has_incomplete_tasks(tasks_path.read_text(encoding="utf-8"))
        except OSError as exc:
            self.log_viewer.append_log(f"Failed to read tasks.md: {exc}", "warning")
            return False

    def _directory_has_non_framework_content(self, path: str) -> bool:
        """Return True when directory has non-framework content worth bootstrapping."""
        ignored_names = {
            ".agentharness",
            ".git",
            ".idea",
            ".vscode",
            ".venv",
            "__pycache__",
            FileManager.TASKS_FILE,
            FileManager.RECENT_CHANGES_FILE,
            FileManager.DESCRIPTION_FILE,
            FileManager.RESEARCH_FILE,
            FileManager.ANSWER_FILE,
            "session_state.json",
            "questions.json",
            FileManager.AGENTS_FILE,
            FileManager.CLAUDE_FILE,
            FileManager.GEMINI_FILE,
            ".gitignore",
            "review",
        }
        try:
            for entry in Path(path).iterdir():
                if entry.name in ignored_names:
                    continue
                return True
        except OSError as exc:
            self.log_viewer.append_log(f"Failed to inspect directory contents: {exc}", "warning")
        return False

    def _prompt_bootstrap_description_choice(self, path: str) -> bool:
        """Ask user whether to auto-generate initial description for an existing folder."""
        reply = QMessageBox.question(
            self,
            "Existing Folder Detected",
            "You selected a non-empty folder.\n\n"
            "Is this an existing project?\n"
            "Would you like to create an initial product description from the current codebase?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        self.log_viewer.append_log(
            f"Initial-description bootstrap prompt for '{path}': "
            f"{'accepted' if reply == QMessageBox.Yes else 'declined'}",
            "info",
        )
        return reply == QMessageBox.Yes

    def _prompt_bootstrap_llm_selection(self) -> tuple[str, str] | None:
        """Open provider/model selection dialog for description bootstrap."""
        providers = LLMProviderRegistry.get_all()
        if not providers:
            QMessageBox.warning(self, "No LLM Providers", "No LLM providers are registered.")
            return None

        dialog = QDialog(self)
        dialog.setWindowTitle("Select LLM for Initial Description")
        dialog.setMinimumWidth(520)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        provider_combo = QComboBox()
        model_combo = QComboBox()
        provider_keys = sorted(providers.keys(), key=lambda name: providers[name].display_name.lower())

        for key in provider_keys:
            provider_combo.addItem(providers[key].display_name, key)

        def refresh_models():
            model_combo.clear()
            provider_name = provider_combo.currentData()
            provider = providers.get(provider_name)
            if not provider:
                return
            models = provider.get_models() or []
            for model_id, display_name in models:
                model_combo.addItem(display_name, model_id)
            if model_combo.count() == 0:
                default_model = provider.get_default_model()
                if default_model:
                    model_combo.addItem(default_model, default_model)

        provider_combo.currentIndexChanged.connect(refresh_models)
        refresh_models()

        ctx = self.state_machine.context
        preferred_provider = str(ctx.llm_config.get("description_molding", "claude"))
        preferred_model = str(ctx.llm_config.get("description_molding_model", ""))
        provider_index = provider_combo.findData(preferred_provider)
        if provider_index >= 0:
            provider_combo.setCurrentIndex(provider_index)
            refresh_models()
        if preferred_model:
            model_index = model_combo.findData(preferred_model)
            if model_index >= 0:
                model_combo.setCurrentIndex(model_index)

        form.addRow("Provider:", provider_combo)
        form.addRow("Model:", model_combo)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.Accepted:
            return None

        return str(provider_combo.currentData()), str(model_combo.currentData() or "")

    def _maybe_offer_initial_description_bootstrap(
        self, path: str, has_non_framework_content: bool, existing_description: str
    ):
        """Offer LLM-generated initial description for non-empty existing projects."""
        if not path or not has_non_framework_content:
            return
        if existing_description.strip():
            return
        normalized_path = str(Path(path))
        if normalized_path in self._description_bootstrap_prompted_paths:
            return
        self._description_bootstrap_prompted_paths.add(normalized_path)
        if not self._prompt_bootstrap_description_choice(path):
            return
        selection = self._prompt_bootstrap_llm_selection()
        if not selection:
            self.log_viewer.append_log("Initial-description bootstrap cancelled.", "info")
            return
        provider_name, model = selection
        self._run_initial_description_bootstrap(provider_name, model)

    def _run_initial_description_bootstrap(self, provider_name: str, model: str):
        """Run an LLM pass that creates product-description.md from existing codebase."""
        if self.current_worker:
            self.log_viewer.append_log(
                "Cannot start initial-description bootstrap while another worker is running.",
                "warning",
            )
            return
        if not self.file_manager:
            self.log_viewer.append_log(
                "Cannot start initial-description bootstrap without an active working directory.",
                "warning",
            )
            return

        try:
            provider = LLMProviderRegistry.get(provider_name)
        except Exception as exc:
            self.log_viewer.append_log(f"Invalid bootstrap LLM provider '{provider_name}': {exc}", "error")
            QMessageBox.warning(self, "Invalid Provider", str(exc))
            return

        prompt = PromptTemplates.format_repository_description_bootstrap_prompt()
        self._description_bootstrap_prev_content = (self._load_description_from_file() or "").strip()
        worker = LLMWorker(
            provider=provider,
            prompt=prompt,
            working_directory=self.state_machine.context.working_directory,
            model=model or None,
            debug_stage="repository_description_bootstrap",
        )
        self._connect_worker_signals(worker)
        worker.signals.result.connect(self.on_initial_description_bootstrap_complete)

        self.current_worker = worker
        self.thread_pool.start(worker)
        self.chat_panel.set_bot_activity("Creating initial description from existing codebase...")
        self.log_viewer.append_log(
            f"Generating initial product description with {provider.display_name}"
            f"{f' ({model})' if model else ''}...",
            "info",
        )
        self.update_button_states()

    @Slot(object)
    def on_initial_description_bootstrap_complete(self, _result):
        """Handle completion of initial description bootstrap generation."""
        self.chat_panel.clear_bot_activity()
        generated = (self._load_description_from_file() or "").strip()
        if not generated:
            self.log_viewer.append_log(
                "Initial-description bootstrap completed but product-description.md is still empty.",
                "warning",
            )
            QMessageBox.warning(
                self,
                "Description Not Generated",
                "The LLM did not produce content for product-description.md.\n"
                "You can enter it manually in chat using 'Create initial description'.",
            )
            return

        self._suppress_description_sync = True
        try:
            self._set_description(generated)
        finally:
            self._suppress_description_sync = False

        self.state_machine.update_context(description=generated)
        self.chat_panel.update_placeholder_text(has_description=True)
        if generated != self._description_bootstrap_prev_content:
            self.log_viewer.append_log("Generated initial product description from repository.", "success")
            self.chat_panel.add_bot_message("Generated initial product description from the existing codebase.")
        else:
            self.log_viewer.append_log(
                "Bootstrap completed; product-description.md content was unchanged.",
                "info",
            )

    def _update_resume_button_visibility(self):
        """Update the resume button visibility based on current state."""
        phase = self.state_machine.phase
        working_dir = self.config_panel.get_working_directory()

        # Show resume button when:
        # 1. Phase is IDLE, COMPLETED, or CANCELLED
        # 2. There are incomplete tasks in tasks.md
        show_button = bool(
            phase in (Phase.IDLE, Phase.COMPLETED, Phase.CANCELLED)
            and working_dir
            and self._working_directory_has_incomplete_tasks(working_dir)
        )

        self.status_panel.set_resume_button_visible(show_button)

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
        ctx = self.state_machine.context

        is_idle = phase == Phase.IDLE
        is_completed = phase == Phase.COMPLETED
        is_cancelled = phase == Phase.CANCELLED
        is_error = phase == Phase.ERROR
        is_running = phase not in (Phase.IDLE, Phase.COMPLETED, Phase.ERROR,
                                   Phase.CANCELLED, Phase.PAUSED, Phase.AWAITING_ANSWERS)
        is_paused = phase == Phase.PAUSED
        is_awaiting = phase == Phase.AWAITING_ANSWERS
        can_start_from_question_flow = (
            is_awaiting and ctx.questions_answered and self.current_worker is None
        )

        # Enable start button when:
        # - loop is not running (idle/paused/completed/cancelled/error)
        # - or question flow has answered questions and is ready to move to planning
        can_start = (
            (is_idle or is_paused or is_completed or is_cancelled or is_error) and self.current_worker is None
        ) or can_start_from_question_flow

        # Update menu bar icon buttons
        try:
            self.menu_start_button.setEnabled(can_start)
            self.menu_start_button.setToolTip(
                ("Resume workflow (Ctrl+Return)" if is_paused else "Start workflow (Ctrl+Return)")
            )
        except RuntimeError:
            pass  # Button may have been deleted by Qt

        try:
            self.menu_pause_button.setEnabled(is_running)
        except RuntimeError:
            pass

        try:
            self.menu_stop_button.setEnabled(is_running or is_paused or is_awaiting)
        except RuntimeError:
            pass

        try:
            self.menu_next_step_button.setEnabled(self._debug_waiting)
        except RuntimeError:
            pass

        # Update workflow menu actions
        self.start_workflow_action.setEnabled(can_start)
        self.start_workflow_action.setText("&Resume" if is_paused else "&Start")
        self.pause_workflow_action.setEnabled(is_running)
        self.stop_workflow_action.setEnabled(is_running or is_paused or is_awaiting)
        self.next_step_action.setEnabled(self._debug_waiting)

        # Update menu bar icon buttons (with safe Qt object check)
        try:
            if hasattr(self, 'menu_start_button') and self.menu_start_button is not None:
                self.menu_start_button.setEnabled(can_start)
                self.menu_start_button.setToolTip(
                    f"{'Resume' if is_paused else 'Start'} workflow (Ctrl+Return)"
                )
                # Update icon
                if is_paused:
                    self.menu_start_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
                else:
                    self.menu_start_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        except RuntimeError:
            # Qt object has been deleted
            pass

        try:
            if hasattr(self, 'menu_pause_button') and self.menu_pause_button is not None:
                self.menu_pause_button.setEnabled(is_running)
        except RuntimeError:
            pass

        try:
            if hasattr(self, 'menu_stop_button') and self.menu_stop_button is not None:
                self.menu_stop_button.setEnabled(is_running or is_paused or is_awaiting)
        except RuntimeError:
            pass

        # Update resume button visibility
        self._update_resume_button_visibility()

        # Also update panel states
        description_editable = is_idle or (is_awaiting and ctx.questions_answered and self.current_worker is None)
        self.description_panel.set_readonly(not description_editable)
        # Description panel is now always in the left tab widget, so no visibility toggle needed
        self.llm_selector_panel.set_enabled(True)
        self.config_panel.set_enabled(is_idle)

        # Enable chat panel when there's a working directory and file manager
        # Chat works during execution (queues for next boundary), when idle, and when completed
        # This allows users to add more tasks or make changes after workflow completion
        chat_enabled = self.file_manager is not None and phase not in [Phase.ERROR, Phase.CANCELLED]
        self.chat_panel.set_input_enabled(chat_enabled)

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
        self._last_worker_status = ""
        self._task_progress_cycle_active = False
        self._task_progress_cycle_baseline_completed = 0

    def _should_show_activity(self, phase: Phase) -> bool:
        """Return True if the activity panel should be visible for this phase."""
        return phase not in (Phase.IDLE, Phase.QUESTION_GENERATION, Phase.AWAITING_ANSWERS)

    def _update_chat_bot_activity(self, phase: Phase, status: str = ""):
        """Update friendly animated activity text in the chat panel based on phase/status."""
        options = self._get_chat_activity_options(phase, status)
        if options:
            self.chat_panel.set_bot_activity_options(options)
            return
        if phase in (
            Phase.IDLE,
            Phase.AWAITING_ANSWERS,
            Phase.COMPLETED,
            Phase.PAUSED,
            Phase.ERROR,
            Phase.CANCELLED,
        ):
            self.chat_panel.clear_bot_activity()

    def _get_chat_activity_options(self, phase: Phase, status: str) -> list[str]:
        """Return rotating friendly activity messages for the current workflow context."""
        status_text = (status or "").strip()
        status_lower = status_text.lower()
        last_status_lower = self._last_worker_status.lower()

        if "processing client message" in status_lower:
            return [
                "Reading your latest message with maximum squint.",
                "Parsing your request and lining up edits.",
                "Translating your ask into actionable changes.",
                "Opening files and wiring your request in.",
                "Queueing your updates and syncing outputs.",
                "Running your request through the tiny project goblins.",
                "Applying requested changes without spilling coffee.",
                "Turning your message into concrete file updates.",
                "Working your request through the pipeline now.",
                "Finishing this message pass and syncing results.",
            ]

        if phase == Phase.QUESTION_GENERATION:
            return [
                "Drafting smart questions so we do not build nonsense.",
                "Interrogating the requirements politely.",
                "Generating clarifying questions with detective energy.",
                "Collecting unknowns before writing risky code.",
                "Building a question set sharper than a linters warning.",
                "Finding ambiguous spots and poking them gently.",
                "Assembling the next question volley.",
                "Turning vague ideas into answerable prompts.",
                "Preparing questions that save us future rework.",
                "Question factory is running at full curiosity.",
            ]

        if phase == Phase.TASK_PLANNING:
            if "research" in status_lower:
                return [
                    "Research phase is mapping the problem space.",
                    "Gathering implementation notes from description and tasks.",
                    "Building research context to guide clean execution.",
                    "Analyzing constraints before coding starts.",
                    "Research pass is filling in product and domain details.",
                    "Collecting references and edge cases for the next loop.",
                    "Turning planned tasks into focused technical context.",
                    "Researching now so implementation decisions are less risky.",
                    "Preparing deeper context for the execution phase.",
                    "Compiling practical research notes into research.md.",
                ]
            return [
                "Breaking work into bite-size tasks for this run.",
                "Building the task plan like tiny LEGO bricks.",
                "Converting requirements into executable checklist items.",
                "Sequencing tasks to avoid chaos-induced bugs.",
                "Planning now so future-us can sleep later.",
                "Turning scope into practical next steps.",
                "Structuring the backlog with ruthless pragmatism.",
                "Designing a task list that actually ships.",
                "Organizing steps so the loop can move fast.",
                "Task planner is mapping the route.",
            ]

        if phase == Phase.MAIN_EXECUTION:
            if status_lower.startswith("executing:"):
                task_text = status_text.split(":", 1)[1].strip()
                if task_text:
                    return [
                        f"Implementing now: {task_text}",
                        f"Wrestling this task into done: {task_text}",
                        f"Shipping code for: {task_text}",
                        f"Keyboard is in overdrive for: {task_text}",
                        f"Turning TODO into DONE: {task_text}",
                        f"Refactoring reality around: {task_text}",
                        f"Running build-brain on: {task_text}",
                        f"Polishing this task until it behaves: {task_text}",
                        f"Coding pass active for: {task_text}",
                        f"Advancing the checklist with: {task_text}",
                    ]
            return [
                "Executing tasks and collecting tiny victories.",
                "Pushing code changes through this iteration.",
                "Implementing the next checklist item now.",
                "Making progress one commit-worthy chunk at a time.",
                "Coding in a straight line toward done.",
                "Advancing the main loop with fresh edits.",
                "Working through implementation details now.",
                "Converting plan into running code.",
                "Putting features where the TODOs used to be.",
                "Current mode: practical code generation.",
            ]

        if phase == Phase.DEBUG_REVIEW:
            if "unit test prep" in status_lower:
                return [
                    "Warming up unit tests before review starts.",
                    "Teaching tests new tricks for recent changes.",
                    "Preparing a test baseline so review can focus.",
                    "Updating tests to keep regressions unemployed.",
                    "Fortifying unit tests before reviewer mode.",
                    "Tuning test coverage with surgical keyboard taps.",
                    "Making sure tests and code still speak the same language.",
                    "Laying test guardrails for the next pass.",
                    "Unit-test prep is sharpening its tiny knives.",
                    "Testing scaffolding is being aligned now.",
                ]
            if status_lower.startswith("review:"):
                review_name = status_text.split(":", 1)[1].strip()
                transition_line = "Unit tests done, reviewer hat is now on."
                if not last_status_lower.startswith("unit test prep"):
                    transition_line = "Reviewing latest changes with bug-hunting goggles."
                if review_name:
                    return [
                        transition_line,
                        f"Running {review_name} checks for sneaky issues.",
                        f"Inspecting {review_name} quality signals now.",
                        f"Review lane active: {review_name}.",
                        f"Scanning {review_name} for footguns and oddities.",
                        f"Putting {review_name} under the microscope.",
                        f"Hunting edge cases in {review_name}.",
                        f"Reviewing {review_name} with mild paranoia.",
                        f"Applying reviewer skepticism to {review_name}.",
                        f"Cross-checking {review_name} behavior and structure.",
                    ]
                return [
                    "Reviewing the latest changes with bug-hunting goggles.",
                    "Review checks in progress.",
                    "Inspecting code quality and behavior.",
                    "Looking for regressions and risky assumptions.",
                    "Running a full review sweep.",
                    "Poking weak spots before they poke production.",
                    "Checking correctness, clarity, and maintainability.",
                    "Review pass underway with strict standards.",
                    "Evaluating changes for hidden side effects.",
                    "Running quality gate checks now.",
                ]
            if status_lower.startswith("fixing:"):
                review_name = status_text.split(":", 1)[1].strip()
                if review_name:
                    return [
                        f"Applying {review_name} fixes one by one.",
                        f"Resolving findings from {review_name}.",
                        f"Patching issues flagged by {review_name}.",
                        f"Turning {review_name} review comments into code changes.",
                        f"Fix pass active for {review_name}.",
                        f"Cleaning up defects found in {review_name}.",
                        f"Repair cycle engaged: {review_name}.",
                        f"Closing {review_name} review items now.",
                        f"Fixing what {review_name} complained about.",
                        f"Converting {review_name} findings into green checks.",
                    ]
                return [
                    "Applying fixes from review feedback.",
                    "Resolving issues from the latest review pass.",
                    "Patching findings with minimal drama.",
                    "Fix cycle in progress.",
                    "Closing review gaps and tightening behavior.",
                    "Addressing quality findings now.",
                    "Repairing issues before the next loop step.",
                    "Fixing defects with deterministic intent.",
                    "Turning review notes into merged reality.",
                    "Patch set underway for reviewer findings.",
                ]
            return [
                "Review cycle in progress.",
                "Analyzing changes for quality and risks.",
                "Running reviewer checks now.",
                "Scanning for regressions and brittle logic.",
                "Checking safety rails and behavior edges.",
                "Reviewing implementation choices critically.",
                "Quality gate is actively judging the diff.",
                "Pulling on loose threads in the patch.",
                "Risk audit underway for current changes.",
                "Review bot is in serious mode.",
            ]

        if phase in (Phase.GIT_OPERATIONS, Phase.AWAITING_GIT_APPROVAL):
            if "generating commit message" in status_lower:
                return [
                    "Writing a commit message that future-us can trust.",
                    "Summarizing this diff without fiction.",
                    "Drafting commit text from the latest changes.",
                    "Composing commit poetry (strictly technical edition).",
                    "Packaging edits into an understandable commit summary.",
                    "Turning diff noise into clear human words.",
                    "Generating commit message with context and restraint.",
                    "Naming this batch of changes responsibly.",
                    "Preparing a concise commit narrative.",
                    "Building commit text from evidence in the diff.",
                ]
            if "committing changes" in status_lower:
                return [
                    "Committing the latest updates.",
                    "Saving this iteration to git history.",
                    "Sealing changes into local history.",
                    "Recording this work in the timeline.",
                    "Committing now, blame annotations loading...",
                    "Locking in this patch set.",
                    "Capturing the diff in a commit snapshot.",
                    "Making this iteration officially versioned.",
                    "Writing changes into git memory.",
                    "Finalizing commit metadata and content.",
                ]
            if "pushing changes" in status_lower:
                return [
                    "Pushing updates to the remote repository.",
                    "Syncing this commit upstream.",
                    "Publishing latest changes to origin.",
                    "Sending fresh commits to their cloud apartment.",
                    "Remote sync in progress, fingers crossed.",
                    "Uploading this iteration to shared history.",
                    "Shipping commits upstream now.",
                    "Propagating local truth to remote truth.",
                    "Pushing branch updates over the wire.",
                    "Making sure origin sees what we changed.",
                ]
            return [
                "Wrapping up git operations.",
                "Preparing repository state for the next step.",
                "Finishing repository housekeeping.",
                "Tidying repository metadata and status.",
                "Final git checks before continuing the loop.",
                "Closing out source-control chores.",
                "Repo maintenance mode is active.",
                "Making git state clean for the next phase.",
                "Completing VCS bookkeeping tasks.",
                "Git phase is doing its paperwork.",
            ]

        return []

    def _get_agent_label(self, phase: Phase) -> str:
        """Build a compact agent label for the current phase."""
        ctx = self.state_machine.context
        config = ctx.llm_config
        if phase == Phase.TASK_PLANNING:
            return (
                f"Planner: {config.get('task_planning', 'N/A')} | "
                f"Research: {config.get('research', 'N/A')}"
            )
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

    def _is_main_loop_phase(self, phase: Phase) -> bool:
        """Return True when the UI should prioritize live task loop status."""
        return phase in (
            Phase.MAIN_EXECUTION,
            Phase.DEBUG_REVIEW,
            Phase.GIT_OPERATIONS,
            Phase.AWAITING_GIT_APPROVAL,
            Phase.COMPLETED,
        )

    def _refresh_task_display(self):
        """Refresh task list display in the Tasks tab (wrapper for _refresh_task_loop_snapshot)."""
        self._refresh_task_loop_snapshot()

    def _begin_task_progress_cycle(self):
        """Start a new per-task progress cycle at the beginning of main execution."""
        baseline = 0
        if self.file_manager:
            try:
                tasks_content = self.file_manager.read_tasks()
                tasks = parse_tasks(tasks_content)
                baseline = sum(1 for task in tasks if task.completed)
            except Exception:
                baseline = 0
        self._task_progress_cycle_baseline_completed = max(0, baseline)
        self._task_progress_cycle_active = True

    def _get_task_phase_progress_weight(self, phase: Phase, action_text: str) -> float:
        """Return phase weight for earned progress on tasks completed in the current cycle."""
        action_lower = (action_text or "").lower()
        if phase == Phase.MAIN_EXECUTION:
            return 0.45
        if phase == Phase.DEBUG_REVIEW:
            return 0.80
        if phase in (Phase.GIT_OPERATIONS, Phase.AWAITING_GIT_APPROVAL):
            if "git operations finished" in action_lower:
                return 1.0
            if "pushing changes" in action_lower:
                return 0.98
            if "committing changes" in action_lower:
                return 0.96
            if "generating commit message" in action_lower:
                return 0.90
            return 0.92
        return 1.0

    def _get_display_completed_progress(self, completed_count: int, total_count: int, action_text: str) -> float:
        """Return progress-completed value that is phase-weighted during active loop work."""
        if total_count <= 0:
            return 0.0

        phase = self.state_machine.phase
        if phase == Phase.COMPLETED:
            return float(completed_count)

        if phase not in (Phase.MAIN_EXECUTION, Phase.DEBUG_REVIEW, Phase.GIT_OPERATIONS, Phase.AWAITING_GIT_APPROVAL):
            return float(completed_count)

        if not self._task_progress_cycle_active:
            self._task_progress_cycle_baseline_completed = completed_count
            self._task_progress_cycle_active = True

        if completed_count < self._task_progress_cycle_baseline_completed:
            self._task_progress_cycle_baseline_completed = completed_count

        newly_completed = max(0, completed_count - self._task_progress_cycle_baseline_completed)
        if newly_completed == 0:
            return float(completed_count)

        weight = self._get_task_phase_progress_weight(phase, action_text)
        weighted_completed = self._task_progress_cycle_baseline_completed + (newly_completed * weight)
        return max(0.0, min(float(completed_count), weighted_completed))

    def _refresh_task_loop_snapshot(self, action: str = ""):
        """Refresh task list in description panel and task-based top-right progress."""
        if not self.file_manager:
            self.description_panel.set_tasks([], [])
            self.description_panel.set_current_action("Waiting")
            self.status_panel.set_task_progress(0, 0)
            return

        try:
            tasks_content = self.file_manager.read_tasks()
        except Exception as exc:
            self.log_viewer.append_log(f"Failed to read tasks.md for UI update: {exc}", "warning")
            return

        tasks = parse_tasks(tasks_content)
        completed_tasks = [task.text for task in tasks if task.completed]
        incomplete_tasks = [task.text for task in tasks if not task.completed]

        self.description_panel.set_tasks(completed_tasks, incomplete_tasks)
        current_action = action or self.activity_state.get("action") or self.status_panel.sub_status_label.text()
        display_completed = self._get_display_completed_progress(
            completed_count=len(completed_tasks),
            total_count=len(tasks),
            action_text=current_action
        )
        self.status_panel.set_task_progress(display_completed, len(tasks))
        self.description_panel.set_current_action(current_action)

    def _update_loop_priority_visibility(self, phase: Phase):
        """Switch to task list view during main loop phases."""
        if self._is_main_loop_phase(phase):
            # Automatically enable Tasks tab during main loop phases
            if not self._tasks_enabled:
                self._tasks_enabled = True
                if hasattr(self, "show_tasks_action"):
                    self.show_tasks_action.setChecked(True)
                self._update_left_tabs()
            self.description_panel._set_mode("task_list")
            self._refresh_task_loop_snapshot()
            return
        self._task_progress_cycle_active = False
        self._task_progress_cycle_baseline_completed = 0
        self.status_panel.set_task_progress(0, 0)

    # Status panel is always visible - no toggle needed

    @Slot(bool)
    def on_toggle_logs(self, enabled: bool):
        """Show/hide logs tab in left panel."""
        self._logs_enabled = enabled
        self._logs_panel_visible = enabled  # Keep in sync for settings persistence
        self._update_left_tabs()

    @Slot(bool)
    def on_toggle_description(self, enabled: bool):
        """Show/hide description tab in left panel."""
        self._description_enabled = enabled
        self._sync_description_to_left_preview()
        self._update_left_tabs()

    @Slot(bool)
    def on_toggle_tasks(self, enabled: bool):
        """Show/hide tasks tab in left panel."""
        self._tasks_enabled = enabled
        self._update_left_tabs()

    @Slot(str)
    def on_client_message_sent(self, message: str, update_description: bool = False,
                                add_tasks: bool = False, provide_answer: bool = False):
        """Handle user sending a client message with checkbox options."""
        import uuid
        from datetime import datetime

        description = self._get_description()
        if not description or not description.strip():
            existing = self._load_description_from_file()
            if existing and existing.strip():
                # Keep chat routing aligned with persisted project state.
                self._set_description(existing)
                self.state_machine.update_context(description=existing)
                self.chat_panel.update_placeholder_text(has_description=True)
                description = existing
                self.log_viewer.append_log(
                    "Loaded existing product-description.md before handling chat message.",
                    "info",
                )
        message_id = str(uuid.uuid4())

        # Case 1: Empty description - direct initialization
        if not description or not description.strip():
            self.chat_panel.add_message(message_id, message, "processing")
            self._initial_description_message_id = message_id
            self.log_viewer.append_log("Initializing product description from chat message...", "info")
            working_dir = self.config_panel.get_working_directory()
            if working_dir:
                limit = self.config_panel.chat_history_limit_spin.value()
                ChatHistoryManager.append_message(working_dir, "user", message, limit=limit)
            self._initialize_description_from_chat(message)
            return

        # Case 2: Non-empty description - queue for LLM processing
        # Add to state context queue with checkbox states
        ctx = self.state_machine.context
        ctx.pending_client_messages.append({
            "id": message_id,
            "content": message,
            "timestamp": datetime.now().isoformat(),
            "status": "queued",
            "update_description": update_description,
            "add_tasks": add_tasks,
            "provide_answer": provide_answer
        })

        # Update UI
        self.chat_panel.add_message(message_id, message, "queued")

        # Persist user message to history
        working_dir = self.config_panel.get_working_directory()
        if working_dir:
            limit = self.config_panel.chat_history_limit_spin.value()
            ChatHistoryManager.append_message(working_dir, "user", message, limit=limit)

        # Log which actions are requested
        actions = []
        if update_description:
            actions.append("update description")
        if add_tasks:
            actions.append("add tasks")
        if provide_answer:
            actions.append("provide answer")

        actions_str = ", ".join(actions) if actions else "direct message"
        self.log_viewer.append_log(f"Client message queued ({actions_str}): {message[:50]}...", "info")

        # If not in active workflow execution, process immediately
        phase = self.state_machine.phase
        if phase not in [Phase.MAIN_EXECUTION, Phase.DEBUG_REVIEW, Phase.GIT_OPERATIONS]:
            self.log_viewer.append_log("Processing message immediately (workflow not running)...", "info")
            self._process_client_messages()

    @Slot()
    def on_clear_chat_history(self):
        """Clear chat history file and display."""
        working_dir = self.config_panel.get_working_directory()
        if working_dir:
            ChatHistoryManager.clear(working_dir)
        self.chat_panel.clear_display()

    @Slot(str)
    def on_bot_message_added(self, content: str):
        """Persist bot message to chat history."""
        working_dir = self.config_panel.get_working_directory()
        if working_dir:
            limit = self.config_panel.chat_history_limit_spin.value()
            ChatHistoryManager.append_message(working_dir, "bot", content, limit=limit)

    def _get_description(self) -> str:
        """Get the current description content."""
        return self._description_content

    def _set_description(self, content: str):
        """Set the description content and sync to preview."""
        self._description_content = content
        self._sync_description_to_left_preview()

    def _apply_edited_description(self, content: str):
        """Apply direct edits from the post-question decision dialog."""
        text = (content or "").strip()
        self._set_description(text)
        self.state_machine.update_context(description=text)
        self._sync_description_to_file(text)
        self.log_viewer.append_log("Updated product description from edit dialog.", "success")

    def _sync_description_to_left_preview(self):
        """Sync description content to left tab preview."""
        if hasattr(self, "left_description_preview"):
            self.left_description_preview.setMarkdown(self._description_content)

    def _update_left_tabs(self):
        """Update left tab widget visibility and tabs based on enabled flags."""
        if not hasattr(self, "left_tab_widget"):
            return

        # Remove all tabs
        while self.left_tab_widget.count() > 0:
            self.left_tab_widget.removeTab(0)

        # Add enabled tabs in order
        if self._logs_enabled:
            self.left_tab_widget.addTab(self.log_viewer, "Logs")

        if self._description_enabled:
            self.left_tab_widget.addTab(self.left_description_preview, "Description")

        if self._tasks_enabled:
            self.left_tab_widget.addTab(self.description_panel, "Tasks")
            # Load existing tasks from tasks.md when tab is enabled
            self._refresh_task_display()

        # Show left panel if at least one tab is enabled
        should_show = self._logs_enabled or self._description_enabled or self._tasks_enabled

        splitter = self.left_tab_widget.parentWidget()
        if not isinstance(splitter, QSplitter):
            self.left_tab_widget.setVisible(should_show)
            return

        previous_sizes = splitter.sizes()
        self.left_tab_widget.setVisible(should_show)

        if should_show:
            # Restore previous sizes or use default
            if (
                hasattr(self, "_last_main_splitter_sizes") and
                self._last_main_splitter_sizes and
                len(self._last_main_splitter_sizes) == len(previous_sizes)
            ):
                splitter.setSizes(self._last_main_splitter_sizes)
            elif len(previous_sizes) >= 2 and previous_sizes[0] == 0:
                splitter.setSizes([480, 720])
        else:
            # Hide left panel
            if len(previous_sizes) >= 2 and previous_sizes[0] > 0:
                self._last_main_splitter_sizes = previous_sizes
                right_width = previous_sizes[1] if previous_sizes[1] > 0 else sum(previous_sizes)
            else:
                right_width = sum(previous_sizes) if previous_sizes else 1
            splitter.setSizes([0, max(1, right_width)])

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
        try:
            self.menu_next_step_button.setEnabled(waiting)
        except RuntimeError:
            pass  # Button may have been deleted by Qt
        self.next_step_action.setEnabled(waiting)

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
        phase = self.state_machine.phase
        ctx = self.state_machine.context

        if phase == Phase.AWAITING_ANSWERS and ctx.questions_answered and self.current_worker is None:
            self.log_viewer.append_log("Continuing from answered questions to task planning...", "info")
            self.on_start_planning_requested()
            return

        if phase == Phase.PAUSED:
            # Resume from pause
            self.resume_workflow()
        else:
            # Start new workflow
            self.start_workflow()

    def start_workflow(self):
        """Start a new workflow from the beginning."""
        self._release_debug_wait()

        # Initialize state
        working_dir = self.config_panel.get_working_directory()
        config = self.config_panel.get_config()

        # Check if we're resuming incomplete tasks
        resume_incomplete_tasks = (
            self._resume_incomplete_tasks_directory == working_dir
            and self._working_directory_has_incomplete_tasks(working_dir)
        )

        # Validate inputs (skip description check if resuming incomplete tasks)
        if not resume_incomplete_tasks and not self._get_description().strip():
            QMessageBox.warning(
                self,
                "Missing Description",
                "Please enter a project description in the chat panel.\n\n"
                "The chat panel is where you describe what you want to build."
            )
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

        llm_config = self.llm_selector_panel.get_config_dict()

        self.state_machine.update_context(
            description=self._get_description(),
            working_directory=working_dir,
            max_iterations=config.max_main_iterations,
            debug_iterations=config.debug_loop_iterations,
            current_iteration=0,
            current_debug_iteration=0,
            current_review_type="",
            tasks_content="",
            error_message=None,
            stop_requested=False,
            pause_requested=False,
            paused_from_phase=None,
            paused_from_sub_phase=None,
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
        self.description_panel.set_tasks([], [])
        self.description_panel.set_current_action("Waiting")
        self.status_panel.set_task_progress(0, 0)

        # Initialize file manager
        self.file_manager = FileManager(working_dir)
        self.session_manager.set_working_directory(working_dir)
        self._sync_description_to_file(self._get_description())

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
        self.log_viewer.append_log(
            f"  Unit Test Prep (runs first): {'enabled' if config.run_unit_test_prep else 'disabled'}",
            "info"
        )
        review_types = config.review_types or []
        review_labels = ", ".join(
            [PromptTemplates.get_review_display_name(r) for r in review_types]
        ) or "(none)"
        self.log_viewer.append_log(f"  Review Types (after unit tests): {review_labels}", "info")
        self.log_viewer.append_log(f"  Git Mode: {self.git_mode}", "info")
        self.log_viewer.append_log(f"  Git Remote: {config.git_remote or '(not set)'}", "info")
        self.log_viewer.append_log("LLM PROVIDERS:", "info")
        self.log_viewer.append_log(f"  Question Gen: {llm_config.get('question_gen', 'N/A')}", "info")
        self.log_viewer.append_log(f"  Description Molding: {llm_config.get('description_molding', 'N/A')}", "info")
        self.log_viewer.append_log(f"  Task Planning: {llm_config.get('task_planning', 'N/A')}", "info")
        self.log_viewer.append_log(f"  Research: {llm_config.get('research', 'N/A')}", "info")
        self.log_viewer.append_log(f"  Coder: {llm_config.get('coder', 'N/A')}", "info")
        self.log_viewer.append_log(f"  Reviewer: {llm_config.get('reviewer', 'N/A')}", "info")
        self.log_viewer.append_log(f"  Fixer: {llm_config.get('fixer', 'N/A')}", "info")
        self.log_viewer.append_log(f"  Git Ops: {llm_config.get('git_ops', 'N/A')}", "info")
        self.log_viewer.append_log("=" * 50, "info")

        if resume_incomplete_tasks:
            self.log_viewer.append_log(
                "Resuming existing incomplete tasks from tasks.md in the selected working directory.",
                "info"
            )
            self.question_panel.clear_question()
            self.question_panel.set_readonly(True)
            self.state_machine.transition_to(Phase.MAIN_EXECUTION)
            self.run_main_execution()
            return

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

            working_dir = self.config_panel.get_working_directory()
            if working_dir and self._working_directory_has_incomplete_tasks(working_dir):
                self._resume_incomplete_tasks_directory = working_dir

            if self.current_worker:
                self.current_worker.cancel()

            self.state_machine.transition_to(Phase.CANCELLED)

    @Slot()
    def on_resume_incomplete_tasks_clicked(self):
        """Resume incomplete tasks from tasks.md."""
        working_dir = self.config_panel.get_working_directory()
        if not working_dir or not self._working_directory_has_incomplete_tasks(working_dir):
            QMessageBox.warning(
                self,
                "No Incomplete Tasks",
                "There are no incomplete tasks to resume."
            )
            return

        # Ask for iteration count
        iterations, ok = self._prompt_iteration_count()
        if ok and iterations > 0:
            self._resume_incomplete_tasks_directory = working_dir
            # Set max iterations for the resume
            self.state_machine.update_context(max_iterations=iterations)
            self.on_start_clicked()
        else:
            self.log_viewer.append_log("Resume cancelled by user.", "info")

    def _prompt_iteration_count(self):
        """
        Prompt user for number of iterations to run.
        Returns (iterations, ok) tuple where ok is True if user accepted.
        """
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QSpinBox, QDialogButtonBox
        from PySide6.QtCore import Qt

        dialog = QDialog(self)
        dialog.setWindowTitle("Set Iteration Count")
        dialog.setMinimumWidth(350)

        layout = QVBoxLayout(dialog)

        message = QLabel("How many iterations would you like to run?")
        message.setWordWrap(True)
        message.setAlignment(Qt.AlignCenter)
        layout.addWidget(message)

        iteration_label = QLabel("Number of iterations:")
        layout.addWidget(iteration_label)

        spin_box = QSpinBox()
        spin_box.setMinimum(1)
        spin_box.setMaximum(999)
        spin_box.setValue(10)
        layout.addWidget(spin_box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        result = dialog.exec()

        if result == QDialog.Accepted:
            return spin_box.value(), True
        else:
            return 0, False

    def _prompt_continue_iterations(self):
        """Prompt user to continue with more iterations when max is reached but tasks remain."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QSpinBox, QDialogButtonBox
        from PySide6.QtCore import Qt

        ctx = self.state_machine.context
        completed = ctx.current_iteration
        total = ctx.max_iterations

        # Play notification sound
        QApplication.beep()

        dialog = QDialog(self)
        dialog.setWindowTitle("Iterations Complete")
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout(dialog)

        message = QLabel(
            f"{completed}/{total} iterations complete.\n\n"
            "There are still tasks incomplete.\n"
            "Would you like to keep going?"
        )
        message.setWordWrap(True)
        message.setAlignment(Qt.AlignCenter)
        layout.addWidget(message)

        iteration_label = QLabel("Additional iterations:")
        layout.addWidget(iteration_label)

        spin_box = QSpinBox()
        spin_box.setMinimum(1)
        spin_box.setMaximum(999)
        spin_box.setValue(10)
        layout.addWidget(spin_box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Yes | QDialogButtonBox.No
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        result = dialog.exec()

        if result == QDialog.Accepted:
            additional_iterations = spin_box.value()
            new_max = ctx.current_iteration + additional_iterations
            self.log_viewer.append_log(
                f"User chose to continue with {additional_iterations} more iterations (new max: {new_max})",
                "info"
            )
            self.state_machine.update_context(max_iterations=new_max)
            # Continue execution
            self.run_main_execution()
        else:
            self.log_viewer.append_log("User chose to stop at max iterations", "info")
            self.state_machine.transition_to(Phase.COMPLETED)

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
        else:
            self.status_panel.set_sub_status("")

        self.log_viewer.append_phase(phase_name)
        self.update_button_states()
        self._update_loop_priority_visibility(phase)
        self._update_chat_bot_activity(phase, sub_name)

        if phase_changed and phase == Phase.MAIN_EXECUTION:
            self._begin_task_progress_cycle()

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
            self._refresh_task_loop_snapshot(action=self.activity_state["action"])

    @Slot(str)
    def on_worker_status(self, status: str):
        """Handle worker status updates for UI panels."""
        self.status_panel.set_sub_status(status)
        self._update_chat_bot_activity(self.state_machine.phase, status)

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
        self._refresh_task_loop_snapshot(action=status)
        self._last_worker_status = status

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
        self.chat_panel.clear_bot_activity()
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
        self._refresh_task_loop_snapshot(action="Workflow completed")

    @Slot(str)
    def on_working_dir_changed(self, path: str):
        """Handle working directory change."""
        if not path:
            return
        path_obj = Path(path)
        if not path_obj.exists() or not path_obj.is_dir():
            return

        has_non_framework_content = self._directory_has_non_framework_content(path)
        self._resume_incomplete_tasks_directory = ""
        self.state_machine.update_context(working_directory=path)
        self._prepare_working_directory(path)
        self.description_panel.set_tasks([], [])
        self.description_panel.set_current_action("Waiting")
        self.status_panel.set_task_progress(0, 0)
        existing = self._load_description_from_file()
        if existing:
            self._set_description(existing)
            self.state_machine.update_context(description=existing)
        else:
            self._sync_description_to_file(self._get_description())

        # Update chat panel placeholder text based on whether description exists
        has_description = bool(existing and existing.strip())
        self.chat_panel.update_placeholder_text(has_description=has_description)
        self._maybe_offer_initial_description_bootstrap(path, has_non_framework_content, existing)

        # Load chat history for this project
        history = ChatHistoryManager.load(path)
        self.chat_panel.load_history(history)

        # Load existing tasks if Tasks tab is enabled
        if self._tasks_enabled:
            self._refresh_task_display()

        # Start watching for external changes to product-description.md
        self.description_watcher.start_watching(path)

        if self._working_directory_has_incomplete_tasks(path):
            reply = QMessageBox.question(
                self,
                "Incomplete Tasks Found",
                "There are incomplete tasks in this project.\n"
                "Would you like to complete them?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                # Ask for iteration count
                iterations, ok = self._prompt_iteration_count()
                if ok and iterations > 0:
                    self._resume_incomplete_tasks_directory = path
                    # Set max iterations for the resume
                    self.state_machine.update_context(max_iterations=iterations)
                    self.log_viewer.append_log(
                        f"Resuming incomplete tasks with {iterations} iterations...",
                        "info"
                    )
                    # Automatically start the workflow
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(100, self.on_start_clicked)
                else:
                    self.log_viewer.append_log("Resume cancelled by user (no iterations specified).", "info")
                    self._resume_incomplete_tasks_directory = ""
            else:
                self.log_viewer.append_log("Resume declined by user.", "info")
                self._resume_incomplete_tasks_directory = ""

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

        # Update button and chat states after directory change
        self.update_button_states()

    def load_saved_session(self):
        """Load and restore a saved session."""
        try:
            self.session_manager.load_session(self.state_machine)
            ctx = self.state_machine.context

            # Restore UI state
            self._set_description(ctx.description)
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
            self._update_loop_priority_visibility(self.state_machine.phase)
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

        description = self._get_description()
        self.state_machine.update_context(
            qa_pairs=updated_pairs,
            answers=answers,
            questions_answered=True,
            description=description
        )
        # Rewriting product-description.md in the background is expected here.
        self._suppress_external_description_prompt = True
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
                    description=self._get_description()
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
        description = self._get_description()
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

        self.chat_panel.set_bot_activity("Generating questions...")
        self.log_viewer.append_log("Generating question batch...", "info")
        self.question_panel.show_generating_message()
        self.state_machine.transition_to(Phase.QUESTION_GENERATION, SubPhase.GENERATING_QUESTIONS)

    def run_definition_rewrite(self):
        """Rewrite the description from Q&A before generating more questions."""
        ctx = self.state_machine.context
        if not ctx.qa_pairs:
            self._suppress_external_description_prompt = False
            self.run_question_generation()
            return

        worker = DefinitionRewriteWorker(
            description=self._get_description(),
            qa_pairs=ctx.qa_pairs,
            provider_name=ctx.llm_config.get("description_molding", "claude"),
            working_directory=ctx.working_directory,
            model=ctx.llm_config.get("description_molding_model", "claude-sonnet-4-6")
        )

        self._connect_worker_signals(worker)
        worker.signals.result.connect(self.on_definition_rewrite_ready)

        self.current_worker = worker
        self.thread_pool.start(worker)

    @Slot(str)
    def on_definition_rewrite_ready(self, definition: str):
        """Handle completion of the product definition rewrite."""
        self._suppress_external_description_prompt = False
        updated = self._load_rewritten_description_from_file() or (definition or "").strip()
        if updated:
            self._suppress_description_sync = True
            try:
                self._set_description(updated)
            finally:
                self._suppress_description_sync = False
            self.state_machine.update_context(
                description=updated,
                qa_pairs=[],
                answers={}
            )
            self._sync_description_to_file(updated)
            self.log_viewer.append_log("Updated product description from Q&A rewrite", "success")
            self.chat_panel.add_bot_message("Updated product description from your answers.")
        else:
            self.log_viewer.append_log(
                "Definition rewrite returned empty output; using existing description",
                "warning"
            )
            self.chat_panel.add_bot_message(
                "Saved your answers. Product description was not changed."
            )
        self.state_machine.set_sub_phase(SubPhase.NONE)
        self.question_panel.show_answers_saved()

    # on_description_changed removed - description updates now come through chat workflow
    # Description panel is always read-only; updates handled by chat_to_description flow

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
            content = text.strip() + "\n" if text else ""
            self.file_manager.write_file("product-description.md", content)
            # Update file watcher to avoid treating our own write as external change
            self.description_watcher.update_known_content(content)
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

    def _initialize_description_from_chat(self, message: str):
        """Initialize product description from first chat message."""
        ctx = self.state_machine.context
        if not ctx.working_directory:
            self.log_viewer.append_log("No working directory set - cannot initialize description", "error")
            if self._initial_description_message_id:
                self.chat_panel.update_message_status(self._initial_description_message_id, "failed")
                self.chat_panel.add_answer(
                    self._initial_description_message_id,
                    "Could not initialize product description (no working directory)."
                )
                self._initial_description_message_id = None
            return

        initial_description = (message or "").strip()
        if not initial_description:
            self.log_viewer.append_log("First message was empty - cannot initialize description", "warning")
            if self._initial_description_message_id:
                self.chat_panel.update_message_status(self._initial_description_message_id, "failed")
                self.chat_panel.add_answer(self._initial_description_message_id, "Could not initialize product description.")
                self._initial_description_message_id = None
            return

        self.log_viewer.append_log(
            "Storing first message as original product description before question generation...",
            "info"
        )

        # Keep the first message as-is so clarifying questions are based on the original request.
        self._suppress_description_sync = True
        try:
            self._set_description(initial_description)
        finally:
            self._suppress_description_sync = False

        self._sync_description_to_file(initial_description)
        self.state_machine.update_context(description=initial_description)
        self.description_watcher.update_known_content(initial_description)
        self.chat_panel.update_placeholder_text(has_description=True)

        if self._initial_description_message_id:
            self.chat_panel.update_message_status(self._initial_description_message_id, "completed")
            self.chat_panel.add_answer(
                self._initial_description_message_id,
                "Saved initial product description."
            )
            self._initial_description_message_id = None

        self.log_viewer.append_log("Product description initialized successfully", "success")

        # Auto-trigger question generation if max_questions > 0
        config = self.config_panel.get_config()
        if config.max_questions > 0:
            self.log_viewer.append_log(
                f"Auto-generating {config.max_questions} clarifying questions...",
                "info"
            )
            self.run_question_generation()

    @Slot(str)
    def _on_description_changed_externally(self, new_content: str):
        """Handle external changes to product-description.md."""
        self.log_viewer.append_log("Product description updated externally", "info")
        incoming = (new_content or "").strip()
        current = self._get_description().strip()

        if incoming == current:
            self.log_viewer.append_log("Ignoring external description change with no content delta", "debug")
            return

        if self._suppress_external_description_prompt:
            self._suppress_description_sync = True
            try:
                self._set_description(incoming)
            finally:
                self._suppress_description_sync = False
            self.state_machine.update_context(description=incoming)
            self.chat_panel.update_placeholder_text(has_description=bool(incoming))
            self.log_viewer.append_log("Loaded expected external description update without prompt", "info")
            return

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle("External Description Change")
        msg.setText("The product description was changed by an external source.")
        msg.setInformativeText(
            "Choose whether to load the external changes or keep your current description."
        )
        load_button = msg.addButton("Load External Changes", QMessageBox.AcceptRole)
        keep_button = msg.addButton("Keep Current Description", QMessageBox.RejectRole)
        msg.setDefaultButton(load_button)
        msg.exec()

        if msg.clickedButton() == keep_button:
            self._sync_description_to_file(self._get_description())
            self.log_viewer.append_log("Kept current description and overwrote external changes", "info")
        else:
            self._suppress_description_sync = True
            try:
                self._set_description(incoming)
            finally:
                self._suppress_description_sync = False
            self.state_machine.update_context(description=incoming)
            self.chat_panel.update_placeholder_text(has_description=bool(incoming))
            self.log_viewer.append_log("Loaded external description changes into the UI", "info")

        # Warn if workflow is running
        if self.state_machine.phase in [Phase.MAIN_EXECUTION, Phase.DEBUG_REVIEW, Phase.GIT_OPERATIONS]:
            self.log_viewer.append_log(
                "Warning: Description edited externally during workflow execution",
                "warning"
            )

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
        question_list = questions.get("questions", [])
        self.chat_panel.clear_bot_activity()
        self.chat_panel.add_bot_message(f"Generated {len(question_list)} questions.")

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
        description = self._get_description()
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

        # Save settings before closing
        self.save_current_working_directory_settings()

        event.accept()
