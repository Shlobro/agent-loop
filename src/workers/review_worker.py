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
                 start_iteration: int = 0):
        super().__init__()
        self.reviewer_provider_name = reviewer_provider_name
        self.fixer_provider_name = fixer_provider_name
        self.working_directory = working_directory
        self.iterations = iterations
        self.start_iteration = start_iteration
        self.current_iteration = start_iteration

    def execute(self):
        """Run the review loop."""
        self.update_status("Starting code review loop...")

        reviewer_provider = LLMProviderRegistry.get(self.reviewer_provider_name)
        fixer_provider = LLMProviderRegistry.get(self.fixer_provider_name)
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
        self.log(f"Starting {review_name} review...", "info")

        # Step 1: Reviewer writes to review.md
        review_prompt = PromptTemplates.get_review_prompt(review_type)

        reviewer_worker = LLMWorker(
            provider=reviewer_provider,
            prompt=review_prompt,
            working_directory=self.working_directory
        )

        reviewer_worker.signals.llm_output.connect(
            lambda line: self.signals.llm_output.emit(f"[Reviewer] {line}")
        )

        reviewer_worker.run()

        if reviewer_worker._is_cancelled or self.should_stop():
            return

        # Step 2: Read review.md
        review_content = file_manager.read_review()

        if not review_content.strip():
            self.log(f"No {review_name} issues found", "success")
            self.signals.review_complete.emit(review_type.value, "no_issues")
            return

        # Step 3: Fixer decides agree/disagree and fixes
        self.update_status(f"Fixing: {review_name}")
        self.log(f"Fixer analyzing {review_name} findings...", "info")

        fixer_prompt = PromptTemplates.format_fixer_prompt(
            review_type=review_name,
            review_content=review_content
        )

        fixer_worker = LLMWorker(
            provider=fixer_provider,
            prompt=fixer_prompt,
            working_directory=self.working_directory
        )

        fixer_worker.signals.llm_output.connect(
            lambda line: self.signals.llm_output.emit(f"[Fixer] {line}")
        )

        fixer_worker.run()

        if fixer_worker._is_cancelled or self.should_stop():
            return

        # Step 4: Truncate review.md
        file_manager.truncate_review()

        self.log(f"Completed {review_name} cycle", "success")
        self.signals.review_complete.emit(review_type.value, "complete")
