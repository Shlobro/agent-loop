"""Worker for Phase 5: Git Operations."""

from .base_worker import BaseWorker
from .llm_worker import LLMWorker
from ..llm.base_provider import LLMProviderRegistry
from ..llm.prompt_templates import PromptTemplates


class GitWorker(BaseWorker):
    """
    Phase 5 worker: Git operations (add, commit, optionally push).
    """

    def __init__(self, provider_name: str = "claude",
                 working_directory: str = None,
                 auto_push: bool = False):
        super().__init__()
        self.provider_name = provider_name
        self.working_directory = working_directory
        self.auto_push = auto_push

    def execute(self):
        """Run git operations."""
        self.update_status("Performing git operations...")

        provider = LLMProviderRegistry.get(self.provider_name)

        # Step 1: Git add and commit
        self.log("Running git add and commit...", "info")

        commit_prompt = PromptTemplates.GIT_COMMIT

        commit_worker = LLMWorker(
            provider=provider,
            prompt=commit_prompt,
            working_directory=self.working_directory
        )

        commit_worker.signals.llm_output.connect(
            lambda line: self.signals.llm_output.emit(f"[Git] {line}")
        )

        commit_worker.run()

        if commit_worker._is_cancelled or self.should_stop():
            return {"committed": False, "pushed": False}

        self.log("Changes committed", "success")

        # Step 2: Push if auto_push is enabled
        pushed = False
        if self.auto_push:
            self.log("Pushing to remote...", "info")

            push_prompt = PromptTemplates.GIT_PUSH

            push_worker = LLMWorker(
                provider=provider,
                prompt=push_prompt,
                working_directory=self.working_directory
            )

            push_worker.signals.llm_output.connect(
                lambda line: self.signals.llm_output.emit(f"[Git] {line}")
            )

            push_worker.run()

            if not push_worker._is_cancelled:
                pushed = True
                self.log("Changes pushed to remote", "success")
        else:
            self.log("Auto-push disabled. Commit complete, push skipped.", "info")

        return {
            "committed": True,
            "pushed": pushed
        }
