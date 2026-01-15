"""Worker for Phase 4: Debug/Review Loop."""

from .base_worker import BaseWorker
from .llm_worker import LLMWorker
from ..llm.base_provider import LLMProviderRegistry
from ..llm.prompt_templates import PromptTemplates, ReviewType
from ..core.file_manager import FileManager


class ReviewWorker(BaseWorker):
    """
    Phase 4 worker: Debug/Review loop.
    Runs 6 review cycles per iteration (Architecture, Efficiency, Error Handling,
    Safety, Testing, Documentation).
    """

    REVIEW_SEQUENCE = [
        ReviewType.ARCHITECTURE,
        ReviewType.EFFICIENCY,
        ReviewType.ERROR_HANDLING,
        ReviewType.SAFETY,
        ReviewType.TESTING,
        ReviewType.DOCUMENTATION,
    ]

    def __init__(self, reviewer_provider_name: str = "claude",
                 fixer_provider_name: str = "claude",
                 working_directory: str = None,
                 iterations: int = 5,
                 start_iteration: int = 0,
                 reviewer_model: str = None,
                 fixer_model: str = None):
        super().__init__()
        self.reviewer_provider_name = reviewer_provider_name
        self.fixer_provider_name = fixer_provider_name
        self.working_directory = working_directory
        self.iterations = iterations
        self.start_iteration = start_iteration
        self.current_iteration = start_iteration
        self.reviewer_model = reviewer_model
        self.fixer_model = fixer_model

    def execute(self):
        """Run the review loop."""
        self.update_status("Starting code review loop...")
        self.log(f"=== DEBUG/REVIEW PHASE START ===", "phase")
        self.log(f"Working directory: {self.working_directory}", "info")
        self.log(f"Total iterations planned: {self.iterations}, Starting from: {self.start_iteration}", "info")
        self.log(f"Review sequence: {' -> '.join([r.value for r in self.REVIEW_SEQUENCE])}", "info")

        reviewer_provider = LLMProviderRegistry.get(self.reviewer_provider_name)
        fixer_provider = LLMProviderRegistry.get(self.fixer_provider_name)
        self.log(f"Reviewer LLM: {reviewer_provider.display_name}", "info")
        self.log(f"Fixer LLM: {fixer_provider.display_name}", "info")

        file_manager = FileManager(self.working_directory)
        file_manager.ensure_files_exist()

        for iteration in range(self.start_iteration + 1, self.iterations + 1):
            if self.should_stop():
                if self._is_paused:
                    self.log("Review loop paused", "warning")
                    self.wait_if_paused()
                else:
                    self.log("Review loop stopped by user", "warning")
                    break

            self.current_iteration = iteration
            self.update_progress(iteration, self.iterations)
            self.log(f"Debug iteration {iteration}/{self.iterations}", "phase")
            self.log(f"Running 6 review cycles: Architecture, Efficiency, Error Handling, Safety, Testing, Documentation", "debug")

            for review_type in self.REVIEW_SEQUENCE:
                if self.should_stop():
                    break

                self._run_review_cycle(
                    review_type,
                    reviewer_provider,
                    fixer_provider,
                    file_manager,
                    iteration
                )

        self.log(f"=== DEBUG/REVIEW PHASE END ===", "phase")
        self.log(f"Completed {self.current_iteration} review iterations", "info")

        return {
            "review_iterations_completed": self.current_iteration,
            "stopped_early": self._is_cancelled or self._is_paused
        }

    def _run_review_cycle(self, review_type: ReviewType,
                          reviewer_provider, fixer_provider,
                          file_manager: FileManager, iteration: int):
        """Run a single review -> fix cycle."""
        review_name = review_type.value.replace('_', ' ').title()
        self.update_status(f"Review: {review_name}")
        self.log(f"--- {review_name.upper()} REVIEW CYCLE ---", "info")

        # Step 1: Reviewer writes to review.md
        self.log(f"Step 1/4: Running {review_name} reviewer...", "debug")
        review_prompt = PromptTemplates.get_review_prompt(review_type)
        self.log(f"Reviewer prompt length: {len(review_prompt)} chars", "debug")

        reviewer_worker = LLMWorker(
            provider=reviewer_provider,
            prompt=review_prompt,
            working_directory=self.working_directory,
            model=self.reviewer_model
        )

        reviewer_worker.signals.llm_output.connect(
            lambda line: self.signals.llm_output.emit(f"[Reviewer] {line}")
        )

        reviewer_worker.run()

        if reviewer_worker._is_cancelled or self.should_stop():
            self.log(f"Reviewer cancelled or stopped", "warning")
            return

        # Step 2: Read review.md
        self.log(f"Step 2/4: Reading review.md findings...", "debug")
        review_content = file_manager.read_review()

        if not review_content.strip():
            self.log(f"No {review_name} issues found - review.md is empty", "success")
            self.signals.review_complete.emit(review_type.value, "no_issues")
            return

        # Log review findings summary
        review_lines = review_content.strip().split('\n')
        issue_count = sum(1 for line in review_lines if line.strip().startswith(('1.', '2.', '3.', '4.', '5.', '-')))
        self.log(f"Review found ~{issue_count} items ({len(review_content)} chars)", "info")
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
            model=self.fixer_model
        )

        fixer_worker.signals.llm_output.connect(
            lambda line: self.signals.llm_output.emit(f"[Fixer] {line}")
        )

        fixer_worker.run()

        if fixer_worker._is_cancelled or self.should_stop():
            self.log(f"Fixer cancelled or stopped", "warning")
            return

        # Step 4: Truncate review.md
        self.log(f"Step 4/4: Clearing review.md for next cycle...", "debug")
        file_manager.truncate_review()

        self.log(f"Completed {review_name} cycle", "success")
        self.signals.review_complete.emit(review_type.value, "complete")
