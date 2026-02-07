"""Settings-related UI handlers shared by MainWindow."""

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QFileDialog, QMessageBox

from .dialogs.debug_settings_dialog import DebugSettingsDialog
from .widgets.config_panel import ExecutionConfig
from ..core.project_settings import ProjectSettings, ProjectSettingsManager
from ..workers.llm_worker import LLMWorker


class SettingsMixin:
    """Save/load and debug-settings handlers for the main window."""

    @Slot()
    def on_open_debug_settings(self):
        """Open modal debug settings dialog."""
        dialog = DebugSettingsDialog(
            debug_enabled=self.debug_mode_enabled,
            breakpoints=self.debug_breakpoints,
            show_terminals=self.show_llm_terminals,
            parent=self
        )
        if not dialog.exec():
            return
        self.debug_mode_enabled = dialog.get_debug_enabled()
        self.debug_breakpoints = dialog.get_breakpoints()
        self.show_llm_terminals = dialog.get_show_terminals()
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

    @Slot()
    def on_save_settings(self):
        """Handle save settings action."""
        llm_config = self.llm_selector_panel.get_config()
        exec_config = self.config_panel.get_config()
        settings = ProjectSettings(
            question_gen=llm_config.question_gen,
            description_molding=llm_config.description_molding,
            task_planning=llm_config.task_planning,
            coder=llm_config.coder,
            reviewer=llm_config.reviewer,
            fixer=llm_config.fixer,
            unit_test_prep=llm_config.unit_test_prep,
            git_ops=llm_config.git_ops,
            question_gen_model=llm_config.question_gen_model,
            description_molding_model=llm_config.description_molding_model,
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
            max_questions=exec_config.max_questions,
            git_mode=exec_config.git_mode,
            working_directory=exec_config.working_directory,
            git_remote=exec_config.git_remote,
            review_types=exec_config.review_types,
            run_unit_test_prep=exec_config.run_unit_test_prep,
            tasks_per_iteration=exec_config.tasks_per_iteration
        )
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
                llm_config_dict = {
                    "question_gen": settings.question_gen,
                    "description_molding": settings.description_molding,
                    "task_planning": settings.task_planning,
                    "coder": settings.coder,
                    "reviewer": settings.reviewer,
                    "fixer": settings.fixer,
                    "unit_test_prep": settings.unit_test_prep,
                    "git_ops": settings.git_ops,
                    "question_gen_model": settings.question_gen_model,
                    "description_molding_model": settings.description_molding_model,
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
                    tasks_per_iteration=settings.tasks_per_iteration
                )
                self.config_panel.set_config(exec_config)
                self._apply_git_mode(settings.git_mode)
                self.debug_mode_enabled = settings.debug_mode_enabled
                self.debug_breakpoints = settings.debug_breakpoints
                self.show_llm_terminals = settings.show_llm_terminals
                LLMWorker.set_show_live_terminal_windows(self.show_llm_terminals)
                self.state_machine.update_context(
                    debug_mode_enabled=self.debug_mode_enabled,
                    debug_breakpoints=self.debug_breakpoints,
                    show_llm_terminals=self.show_llm_terminals
                )
                self.log_viewer.append_log(f"Settings loaded from: {file_path}", "success")
                QMessageBox.information(self, "Success", "Settings loaded successfully!")
            except Exception as e:
                self.log_viewer.append_log(f"Failed to load settings: {e}", "error")
                QMessageBox.critical(self, "Error", f"Failed to load settings:\n{e}")
