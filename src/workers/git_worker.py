"""Worker for Phase 5: Git Operations."""

import subprocess

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
                 push_enabled: bool = False,
                 git_remote: str = "",
                 model: str = None):
        super().__init__()
        self.provider_name = provider_name
        self.working_directory = working_directory
        self.push_enabled = push_enabled
        self.git_remote = git_remote
        self.model = model

    def execute(self):
        """Run git operations."""
        self.update_status("Performing git operations...")
        self.log(f"=== GIT OPERATIONS PHASE START ===", "phase")
        self.log(f"Working directory: {self.working_directory}", "info")
        self.log(f"Push enabled: {self.push_enabled}", "info")

        try:
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.working_directory,
                capture_output=True,
                text=True,
                check=False
            )
            if status.returncode == 0 and not status.stdout.strip():
                self.log("No changes detected - skipping git operations", "info")
                return {"committed": False, "pushed": False, "skipped": True}
        except OSError as e:
            self.log(f"Failed to check git status: {e}", "warning")

        provider = LLMProviderRegistry.get(self.provider_name)
        self.log(f"Using LLM provider: {provider.display_name}", "info")

        # Step 1: Git add and commit
        self.update_status("Committing changes...")
        self.log("Step 1: Running git add and commit...", "info")
        self.log("LLM will stage all changes and create a commit message", "debug")

        commit_prompt = PromptTemplates.GIT_COMMIT
        self.log(f"Commit prompt: {commit_prompt[:200]}...", "debug")

        commit_worker = LLMWorker(
            provider=provider,
            prompt=commit_prompt,
            working_directory=self.working_directory,
            model=self.model
        )

        commit_worker.signals.llm_output.connect(
            lambda line: self.signals.llm_output.emit(f"[Git] {line}")
        )

        commit_worker.run()

        if commit_worker._is_cancelled or self.should_stop():
            self.log("Git commit cancelled or stopped", "warning")
            return {"committed": False, "pushed": False}

        self.log("Changes committed successfully", "success")

        # Step 2: Push if enabled
        pushed = False
        if self.push_enabled:
            self.update_status("Pushing changes...")
            self.log("Step 2: Pushing to remote...", "info")
            self.log("Push is enabled, will attempt git push", "debug")

            push_prompt = PromptTemplates.format_git_push_prompt(self.git_remote)
            self.log(f"Git remote URL: {self.git_remote or '(not set)'}", "debug")

            push_worker = LLMWorker(
                provider=provider,
                prompt=push_prompt,
                working_directory=self.working_directory,
                model=self.model
            )

            push_worker.signals.llm_output.connect(
                lambda line: self.signals.llm_output.emit(f"[Git] {line}")
            )

            push_worker.run()

            if not push_worker._is_cancelled:
                pushed = True
                self.log("Changes pushed to remote successfully", "success")
            else:
                self.log("Git push was cancelled", "warning")
        else:
            self.update_status("Skipping push (push disabled)")
            self.log("Step 2: Skipping push (push disabled)", "info")

        self.log(f"=== GIT OPERATIONS PHASE END ===", "phase")
        self.log(f"Result: committed={True}, pushed={pushed}", "info")

        return {
            "committed": True,
            "pushed": pushed
        }
