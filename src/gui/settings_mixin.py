"""Settings-related UI handlers shared by MainWindow."""

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QFileDialog, QMessageBox, QSplitter
from pathlib import Path

from .dialogs.configuration_settings_dialog import ConfigurationSettingsDialog
from .dialogs.debug_settings_dialog import DebugSettingsDialog
from .dialogs.llm_settings_dialog import LLMSettingsDialog
from .widgets.config_panel import ExecutionConfig
from ..core.project_settings import ProjectSettings, ProjectSettingsManager
from ..workers.llm_worker import LLMWorker


class SettingsMixin:
    """Save/load and debug-settings handlers for the main window."""
    _settings_sync_suspended = False
    _active_working_directory = ""
    _logs_panel_visible = False
    _last_main_splitter_sizes = None

    def initialize_directory_settings(self, startup_directory: str):
        """Initialize automatic per-directory settings behavior and set startup directory."""
        self._settings_sync_suspended = False
        self._active_working_directory = ""
        # Connect signal before setting directory so we can load settings
        self.config_panel.working_directory_changed.connect(self.on_working_directory_settings_changed)
        if startup_directory:
            # This will trigger on_working_directory_settings_changed which loads settings
            self.config_panel.set_working_directory(startup_directory)
        else:
            self._active_working_directory = self.config_panel.get_working_directory()
        # Note: settings are saved on app quit via aboutToQuit signal in main.py

    def build_current_project_settings(self, working_directory: str = "") -> ProjectSettings:
        """Build a ProjectSettings snapshot from current UI state."""
        llm_config = self.llm_selector_panel.get_config()
        exec_config = self.config_panel.get_config()
        target_working_directory = working_directory or exec_config.working_directory
        return ProjectSettings(
            question_gen=llm_config.question_gen,
            description_molding=llm_config.description_molding,
            research=llm_config.research,
            task_planning=llm_config.task_planning,
            coder=llm_config.coder,
            reviewer=llm_config.reviewer,
            fixer=llm_config.fixer,
            unit_test_prep=llm_config.unit_test_prep,
            git_ops=llm_config.git_ops,
            question_gen_model=llm_config.question_gen_model,
            description_molding_model=llm_config.description_molding_model,
            research_model=llm_config.research_model,
            task_planning_model=llm_config.task_planning_model,
            coder_model=llm_config.coder_model,
            reviewer_model=llm_config.reviewer_model,
            fixer_model=llm_config.fixer_model,
            unit_test_prep_model=llm_config.unit_test_prep_model,
            git_ops_model=llm_config.git_ops_model,
            max_main_iterations=exec_config.max_main_iterations,
            debug_loop_iterations=exec_config.debug_loop_iterations,
            debug_mode_enabled=self.debug_mode_enabled,
            debug_breakpoints=self.debug_breakpoints,
            show_llm_terminals=self.show_llm_terminals,
            show_logs_panel=getattr(self, "_logs_enabled", False),
            show_description_tab=getattr(self, "_description_enabled", False),
            show_tasks_tab=getattr(self, "_tasks_enabled", False),
            max_questions=exec_config.max_questions,
            git_mode=exec_config.git_mode,
            working_directory=target_working_directory,
            git_remote=exec_config.git_remote,
            review_types=exec_config.review_types,
            run_unit_test_prep=exec_config.run_unit_test_prep,
            tasks_per_iteration=exec_config.tasks_per_iteration,
        )

    def _apply_project_settings(self, settings: ProjectSettings):
        """Apply a ProjectSettings object to the current UI state."""
        llm_config_dict = {
            "question_gen": settings.question_gen,
            "description_molding": settings.description_molding,
            "research": settings.research,
            "task_planning": settings.task_planning,
            "coder": settings.coder,
            "reviewer": settings.reviewer,
            "fixer": settings.fixer,
            "unit_test_prep": settings.unit_test_prep,
            "git_ops": settings.git_ops,
            "question_gen_model": settings.question_gen_model,
            "description_molding_model": settings.description_molding_model,
            "research_model": settings.research_model,
            "task_planning_model": settings.task_planning_model,
            "coder_model": settings.coder_model,
            "reviewer_model": settings.reviewer_model,
            "fixer_model": settings.fixer_model,
            "unit_test_prep_model": settings.unit_test_prep_model,
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
            review_types=settings.review_types,
            run_unit_test_prep=settings.run_unit_test_prep,
            tasks_per_iteration=settings.tasks_per_iteration,
        )
        self.config_panel.set_config(exec_config)
        self._apply_git_mode(settings.git_mode)
        self.debug_mode_enabled = settings.debug_mode_enabled
        self.debug_breakpoints = settings.debug_breakpoints
        self.show_llm_terminals = settings.show_llm_terminals
        self._set_logs_panel_visible(settings.show_logs_panel)
        self._set_description_tab_visible(settings.show_description_tab)
        self._set_tasks_tab_visible(settings.show_tasks_tab)
        LLMWorker.set_show_live_terminal_windows(self.show_llm_terminals)
        self.state_machine.update_context(
            debug_mode_enabled=self.debug_mode_enabled,
            debug_breakpoints=self.debug_breakpoints,
            show_llm_terminals=self.show_llm_terminals,
        )

    def _save_settings_for_working_directory(self, working_directory: str) -> bool:
        """Save current settings under the working directory `.agentharness`."""
        target = (working_directory or "").strip()
        if not target:
            return False
        path_obj = Path(target)
        if not path_obj.exists() or not path_obj.is_dir():
            return False
        try:
            settings = self.build_current_project_settings(working_directory=target)
            ProjectSettingsManager.save_for_working_directory(settings, target)
            return True
        except Exception as exc:
            self.log_viewer.append_log(f"Failed to save directory settings: {exc}", "warning")
            return False

    @Slot(str)
    def on_working_directory_settings_changed(self, path: str):
        """Save previous directory settings and load settings for the new directory."""
        target = (path or "").strip()
        if self._settings_sync_suspended or not target:
            return
        if self._active_working_directory and self._active_working_directory != target:
            self._save_settings_for_working_directory(self._active_working_directory)

        path_obj = Path(target)
        if not path_obj.exists() or not path_obj.is_dir():
            return

        self._active_working_directory = target
        if ProjectSettingsManager.has_working_directory_settings(target):
            try:
                self._settings_sync_suspended = True
                settings = ProjectSettingsManager.load_for_working_directory(target)
                settings.working_directory = target
                self._apply_project_settings(settings)
                self.log_viewer.append_log(
                    f"Loaded settings from: {ProjectSettingsManager.get_working_directory_settings_path(target)}",
                    "info",
                )
            except Exception as exc:
                self.log_viewer.append_log(f"Failed to load directory settings: {exc}", "warning")
            finally:
                self._settings_sync_suspended = False
        else:
            self._save_settings_for_working_directory(target)

    def save_current_working_directory_settings(self):
        """Persist current settings into the active working directory file."""
        active = self.config_panel.get_working_directory()
        self._save_settings_for_working_directory(active)

    @Slot()
    def on_open_debug_settings(self):
        """Open modal debug settings dialog."""
        dialog = DebugSettingsDialog(
            debug_enabled=self.debug_mode_enabled,
            breakpoints=self.debug_breakpoints,
            show_terminals=self.show_llm_terminals,
            show_logs_panel=self._logs_panel_visible,
            parent=self
        )
        if not dialog.exec():
            return
        self.debug_mode_enabled = dialog.get_debug_enabled()
        self.debug_breakpoints = dialog.get_breakpoints()
        self.show_llm_terminals = dialog.get_show_terminals()
        self._set_logs_panel_visible(dialog.get_show_logs_panel())
        LLMWorker.set_show_live_terminal_windows(self.show_llm_terminals)
        self.state_machine.update_context(
            debug_mode_enabled=self.debug_mode_enabled,
            debug_breakpoints=self.debug_breakpoints,
            show_llm_terminals=self.show_llm_terminals
        )
        self.log_viewer.append_log(
            f"Debug step mode {'enabled' if self.debug_mode_enabled else 'disabled'}",
            "info"
        )
        self.log_viewer.append_log(
            f"LLM terminal windows {'enabled' if self.show_llm_terminals else 'disabled'}",
            "info"
        )
        self.log_viewer.append_log(
            f"Left logs panel {'enabled' if self._logs_panel_visible else 'disabled'}",
            "info"
        )

    @Slot()
    def on_open_llm_settings(self):
        """Open modal LLM settings dialog."""
        dialog = LLMSettingsDialog(
            current_config=self.llm_selector_panel.get_config_dict(),
            parent=self
        )
        if not dialog.exec():
            return

        self.llm_selector_panel.set_config(dialog.get_config_dict())
        self.on_runtime_llm_config_changed()
        self.log_viewer.append_log("Updated LLM provider/model settings", "info")

    @Slot()
    def on_open_configuration_settings(self):
        """Open modal configuration settings dialog."""
        current_config = self.config_panel.get_config()
        current_config.git_mode = self.git_mode
        dialog = ConfigurationSettingsDialog(
            current_config=current_config,
            parent=self
        )
        dialog.config_panel.set_git_mode(self.git_mode)

        if not dialog.exec():
            return

        updated_config = dialog.get_config()
        self.config_panel.set_config(updated_config)
        self._apply_git_mode(updated_config.git_mode)
        self.on_runtime_config_changed()
        self.log_viewer.append_log("Updated configuration settings", "info")

    def _set_logs_panel_visible(self, visible: bool):
        """Show or hide the logs tab in the left panel."""
        self._logs_panel_visible = bool(visible)
        self._logs_enabled = bool(visible)  # Keep both in sync
        if hasattr(self, "show_logs_action"):
            was_blocked = self.show_logs_action.blockSignals(True)
            self.show_logs_action.setChecked(bool(visible))
            self.show_logs_action.blockSignals(was_blocked)
        if hasattr(self, "_update_left_tabs"):
            self._update_left_tabs()

    def _set_description_tab_visible(self, visible: bool):
        """Show or hide the description tab in the left panel."""
        if hasattr(self, "show_description_action"):
            was_blocked = self.show_description_action.blockSignals(True)
            self.show_description_action.setChecked(bool(visible))
            self.show_description_action.blockSignals(was_blocked)
        if hasattr(self, "_description_enabled"):
            self._description_enabled = bool(visible)
        if hasattr(self, "_update_left_tabs"):
            self._update_left_tabs()

    def _set_tasks_tab_visible(self, visible: bool):
        """Show or hide the tasks tab in the left panel."""
        if hasattr(self, "show_tasks_action"):
            was_blocked = self.show_tasks_action.blockSignals(True)
            self.show_tasks_action.setChecked(bool(visible))
            self.show_tasks_action.blockSignals(was_blocked)
        if hasattr(self, "_tasks_enabled"):
            self._tasks_enabled = bool(visible)
        if hasattr(self, "_update_left_tabs"):
            self._update_left_tabs()

    @Slot()
    def on_save_settings(self):
        """Handle save settings action."""
        settings = self.build_current_project_settings()
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
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Project Settings",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            try:
                settings = ProjectSettingsManager.load_from_file(file_path)
                self._settings_sync_suspended = True
                try:
                    self._apply_project_settings(settings)
                finally:
                    self._settings_sync_suspended = False
                self._active_working_directory = self.config_panel.get_working_directory()
                self._save_settings_for_working_directory(self._active_working_directory)
                self.log_viewer.append_log(f"Settings loaded from: {file_path}", "success")
                QMessageBox.information(self, "Success", "Settings loaded successfully!")
            except Exception as e:
                self.log_viewer.append_log(f"Failed to load settings: {e}", "error")
                QMessageBox.critical(self, "Error", f"Failed to load settings:\n{e}")
