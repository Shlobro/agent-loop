"""Worker for Phase 4: Debug/Review Loop."""

from typing import Callable, Dict, Optional

from .base_worker import BaseWorker
from .llm_worker import LLMWorker
from ..llm.base_provider import LLMProviderRegistry
from ..llm.prompt_templates import PromptTemplates, ReviewType
from ..core.file_manager import FileManager


class ReviewWorker(BaseWorker):
    """
    Phase 4 worker: Debug/Review loop.
    Runs review cycles per iteration based on selected review types.
    """

    def __init__(self, reviewer_provider_name: str = "claude",
                 fixer_provider_name: str = "claude",
                 working_directory: str = None,
                 iterations: int = 1,
                 start_iteration: int = 0,
                 review_types: list = None,
                 run_unit_test_prep: bool = True,
                 reviewer_model: str = None,
                 fixer_model: str = None,
                 runtime_config_provider: Optional[Callable[[], Dict[str, object]]] = None):
        super().__init__()
        self.reviewer_provider_name = reviewer_provider_name
        self.fixer_provider_name = fixer_provider_name
        self.working_directory = working_directory
        self.iterations = iterations
        self.start_iteration = start_iteration
        self.current_iteration = start_iteration
        self.review_sequence = self._build_review_sequence(review_types)
        self.run_unit_test_prep = run_unit_test_prep
        self.reviewer_model = reviewer_model
        self.fixer_model = fixer_model
        self.runtime_config_provider = runtime_config_provider

    def execute(self):
        """Run the review loop."""
        self.update_status("Starting code review loop...")
        self.log(f"=== DEBUG/REVIEW PHASE START ===", "phase")
        self.log(f"Working directory: {self.working_directory}", "info")
        self.log(
            f"Total iterations planned: {self._get_iteration_limit()}, Starting from: {self.start_iteration}",
            "info"
        )
        if self.review_sequence:
            review_sequence_labels = " -> ".join(
                [PromptTemplates.get_review_display_name(r) for r in self.review_sequence]
            )
            self.log(f"Review sequence: {review_sequence_labels}", "info")
        else:
            self.log("Review sequence: (none selected)", "warning")
            return {
                "review_iterations_completed": 0,
                "stopped_early": False
            }

        _, reviewer_model, reviewer_provider = self._get_reviewer_runtime()
        _, fixer_model, fixer_provider = self._get_fixer_runtime()
        self.log(f"Reviewer LLM: {reviewer_provider.display_name}", "info")
        self.log(f"Fixer LLM: {fixer_provider.display_name}", "info")

        file_manager = FileManager(self.working_directory)
        file_manager.ensure_files_exist()
        all_review_files = [
            PromptTemplates.get_review_filename(review_type)
            for review_type in PromptTemplates.get_all_review_types()
        ]
        file_manager.ensure_review_files_exist(all_review_files)
        self.log(
            f"Prepared review files in '{FileManager.REVIEW_DIR}' for {len(all_review_files)} review types",
            "debug"
        )

        if self.run_unit_test_prep:
            if not self._run_pre_review_unit_test_phase(fixer_provider, fixer_model):
                self.log("Pre-review unit test phase interrupted", "warning")
        else:
            self.log("Skipping optional pre-review unit test phase (disabled)", "info")

        iteration = self.start_iteration + 1
        while iteration <= self._get_iteration_limit():
            if self.should_stop():
                if self._is_paused:
                    self.log("Review loop paused", "warning")
                    self.wait_if_paused()
                else:
                    self.log("Review loop stopped by user", "warning")
                    break

            current_limit = max(iteration, self._get_iteration_limit())
            self.current_iteration = iteration
            self.update_progress(iteration, current_limit)
            self.log(f"Debug iteration {iteration}/{current_limit}", "phase")
            review_labels = ", ".join(
                [PromptTemplates.get_review_display_name(r) for r in self.review_sequence]
            )
            self.log(f"Running {len(self.review_sequence)} review cycles: {review_labels}", "debug")

            for review_type in self.review_sequence:
                if self.should_stop():
                    break

                self._run_review_cycle(
                    review_type,
                    file_manager,
                    iteration
                )
            iteration += 1

        self.log(f"=== DEBUG/REVIEW PHASE END ===", "phase")
        self.log(f"Completed {self.current_iteration} review iterations", "info")

        return {
            "review_iterations_completed": self.current_iteration,
            "stopped_early": self._is_cancelled or self._is_paused
        }

    def _build_review_sequence(self, review_types: list) -> list:
        """Build ordered review sequence from selected review type values."""
        if review_types is None:
            review_types = [ReviewType.GENERAL.value]
        selected = set(review_types)
        return [r for r in PromptTemplates.get_all_review_types() if r.value in selected]

    def _run_pre_review_unit_test_phase(self, fixer_provider, fixer_model: str) -> bool:
        """Optionally update unit tests before any review cycles begin."""
        self.update_status("Pre-review: Unit Test Update")
        self.log("--- PRE-REVIEW UNIT TEST UPDATE ---", "info")
        self.log("Running optional unit test update pass using git diff...", "info")

        pre_review_worker = LLMWorker(
            provider=fixer_provider,
            prompt=PromptTemplates.format_pre_review_unit_test_prompt(),
            working_directory=self.working_directory,
            model=fixer_model,
            debug_stage="fixer"
        )
        pre_review_worker.signals.llm_output.connect(
            lambda line: self.signals.llm_output.emit(f"[Unit Test Prep] {line}")
        )
        pre_review_worker.run()

        if pre_review_worker._is_cancelled or self.should_stop():
            return False

        self.log("Completed optional pre-review unit test pass", "success")
        return True

    def _run_review_cycle(self, review_type: ReviewType,
                          file_manager: FileManager, iteration: int):
        """Run a single review -> fix cycle."""
        _, reviewer_model, reviewer_provider = self._get_reviewer_runtime()
        _, fixer_model, fixer_provider = self._get_fixer_runtime()
        review_name = PromptTemplates.get_review_display_name(review_type)
        review_file = PromptTemplates.get_review_filename(review_type)
        file_manager.truncate_review_file(review_file)
        self.update_status(f"Review: {review_name}")
        self.log(f"--- {review_name.upper()} REVIEW CYCLE ---", "info")

        # Step 1: Reviewer writes to review/<type>.md
        self.log(f"Step 1/4: Running {review_name} reviewer -> {review_file}", "debug")
        review_prompt = PromptTemplates.get_review_prompt(review_type, review_file=review_file)
        self.log(f"Reviewer prompt length: {len(review_prompt)} chars", "debug")

        reviewer_worker = LLMWorker(
            provider=reviewer_provider,
            prompt=review_prompt,
            working_directory=self.working_directory,
            model=reviewer_model,
            debug_stage="reviewer"
        )

        reviewer_worker.signals.llm_output.connect(
            lambda line: self.signals.llm_output.emit(f"[Reviewer] {line}")
        )

        reviewer_worker.run()

        if reviewer_worker._is_cancelled or self.should_stop():
            self.log(f"Reviewer cancelled or stopped", "warning")
            return

        # Step 2: Read the review-specific findings file
        self.log(f"Step 2/4: Reading {review_file} findings...", "debug")
        review_content = file_manager.read_review_file(review_file)

        if not review_content.strip():
            self.log(f"No {review_name} issues found - {review_file} is empty", "success")
            file_manager.truncate_review_file(review_file)
            self.signals.review_summary.emit(review_type.value, 0)
            self.signals.review_complete.emit(review_type.value, "no_issues")
            return

        # Log review findings summary
        review_lines = review_content.strip().split('\n')
        issue_count = sum(1 for line in review_lines if line.strip().startswith(('1.', '2.', '3.', '4.', '5.', '-')))
        self.log(f"Review found ~{issue_count} items ({len(review_content)} chars)", "info")
        self.signals.review_summary.emit(review_type.value, issue_count)
        # Show preview of findings
        preview = review_content[:300].replace('\n', ' | ')
        self.log(f"Review preview: {preview}{'...' if len(review_content) > 300 else ''}", "debug")

        # Step 3: Fixer decides agree/disagree and fixes
        self.update_status(f"Fixing: {review_name}")
        self.log(f"Step 3/4: Fixer analyzing {review_name} findings...", "info")

        fixer_prompt = PromptTemplates.format_fixer_prompt(
            review_type=review_name,
            review_content=review_content
        )
        self.log(f"Fixer prompt length: {len(fixer_prompt)} chars", "debug")

        fixer_worker = LLMWorker(
            provider=fixer_provider,
            prompt=fixer_prompt,
            working_directory=self.working_directory,
            model=fixer_model,
            debug_stage="fixer"
        )

        fixer_worker.signals.llm_output.connect(
            lambda line: self.signals.llm_output.emit(f"[Fixer] {line}")
        )

        fixer_worker.run()

        if fixer_worker._is_cancelled or self.should_stop():
            self.log(f"Fixer cancelled or stopped", "warning")
            return

        # Step 4: Truncate the review-specific file
        self.log(f"Step 4/4: Clearing {review_file} for next cycle...", "debug")
        file_manager.truncate_review_file(review_file)

        self.log(f"Completed {review_name} cycle", "success")
        self.signals.review_complete.emit(review_type.value, "complete")

    def _get_runtime_config(self) -> Dict[str, object]:
        """Return live run config when available."""
        if self.runtime_config_provider is None:
            return {}
        try:
            config = self.runtime_config_provider()
        except Exception:
            return {}
        return config if isinstance(config, dict) else {}

    def _get_iteration_limit(self) -> int:
        """Return the current review-iteration limit."""
        runtime = self._get_runtime_config()
        raw_value = runtime.get("debug_iterations", self.iterations)
        try:
            limit = int(raw_value)
        except (TypeError, ValueError):
            limit = self.iterations
        return max(limit, 0)

    def _get_reviewer_runtime(self):
        """Resolve live reviewer provider/model values."""
        runtime = self._get_runtime_config()
        provider_name = str(runtime.get("reviewer", self.reviewer_provider_name))
        model = runtime.get("reviewer_model", self.reviewer_model)
        provider = LLMProviderRegistry.get(provider_name)
        return provider_name, model, provider

    def _get_fixer_runtime(self):
        """Resolve live fixer provider/model values."""
        runtime = self._get_runtime_config()
        provider_name = str(runtime.get("fixer", self.fixer_provider_name))
        model = runtime.get("fixer_model", self.fixer_model)
        provider = LLMProviderRegistry.get(provider_name)
        return provider_name, model, provider
