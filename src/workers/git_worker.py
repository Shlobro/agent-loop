"""Worker for Phase 5: Git Operations."""

import subprocess
from pathlib import Path

from .base_worker import BaseWorker
from .llm_worker import LLMWorker
from ..llm.base_provider import LLMProviderRegistry
from ..llm.prompt_templates import PromptTemplates


class GitWorker(BaseWorker):
    """
    Phase 5 worker: Git operations (add, commit, optionally push).
    """
    COMMIT_MESSAGE_FILE = ".agentharness/git-commit-message.txt"

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

        status = self._run_git_command(["status", "--porcelain"], step_name="status check")
        if not status.stdout.strip():
            self.log("No changes detected - skipping git operations", "info")
            return {"committed": False, "pushed": False, "skipped": True}

        provider = LLMProviderRegistry.get(self.provider_name)
        self.log(f"Using LLM provider: {provider.display_name}", "info")

        # Step 1: Generate commit message using LLM (file output only)
        self.update_status("Generating commit message...")
        self.log("Step 1: Generating commit message file...", "info")
        message_path = self._get_commit_message_path()
        message_path.parent.mkdir(parents=True, exist_ok=True)
        message_path.write_text("", encoding="utf-8")
        relative_message_path = self._relative_message_path(message_path)

        commit_prompt = PromptTemplates.format_git_commit_message_prompt(relative_message_path)
        self.log(f"Commit message prompt: {commit_prompt[:200]}...", "debug")

        commit_worker = LLMWorker(
            provider=provider,
            prompt=commit_prompt,
            working_directory=self.working_directory,
            model=self.model,
            debug_stage="git_commit"
        )

        commit_worker.signals.llm_output.connect(
            lambda line: self.signals.llm_output.emit(f"[Git] {line}")
        )

        commit_worker.run()

        if commit_worker._is_cancelled or self.should_stop():
            self.log("Git commit cancelled or stopped", "warning")
            return {"committed": False, "pushed": False}

        commit_message = message_path.read_text(encoding="utf-8").strip()
        if not commit_message:
            raise RuntimeError(
                f"LLM did not write a commit message to {relative_message_path}"
            )
        commit_message = commit_message.splitlines()[0].strip()
        if not commit_message:
            raise RuntimeError(
                f"Commit message in {relative_message_path} is empty"
            )

        self.log(f"Commit message: {commit_message}", "info")

        # Step 2: Run git add + git commit in code
        self.update_status("Committing changes...")
        self.log("Step 2: Running git add and git commit...", "info")
        self._run_git_command(["add", "."], step_name="git add")
        commit_result = self._run_git_command(
            ["commit", "-m", commit_message],
            step_name="git commit",
            allow_nothing_to_commit=True
        )

        if commit_result.returncode != 0:
            self.log("No commit was created (nothing to commit)", "warning")
            return {"committed": False, "pushed": False, "skipped": True}

        message_path.write_text("", encoding="utf-8")
        self.log("Truncated commit message file after commit", "debug")
        self.log("Changes committed successfully", "success")

        # Step 3: Push if enabled
        pushed = False
        if self.push_enabled:
            self.update_status("Pushing changes...")
            self.log("Step 3: Pushing to remote via git command...", "info")
            self._ensure_remote_config()
            self._run_git_command(["push", "-u", "origin", "HEAD"], step_name="git push")
            pushed = True
            self.log("Changes pushed to remote successfully", "success")
        else:
            self.update_status("Skipping push (push disabled)")
            self.log("Step 3: Skipping push (push disabled)", "info")

        self.log(f"=== GIT OPERATIONS PHASE END ===", "phase")
        self.log(f"Result: committed={True}, pushed={pushed}", "info")

        return {
            "committed": True,
            "pushed": pushed
        }

    def _run_git_command(self, args, step_name: str,
                         allow_nothing_to_commit: bool = False) -> subprocess.CompletedProcess:
        """Run a git command and raise with details on failure."""
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.working_directory,
                capture_output=True,
                text=True,
                check=False
            )
        except OSError as e:
            raise RuntimeError(f"Failed to run {step_name}: {e}") from e

        if result.returncode != 0:
            stderr_text = (result.stderr or "").strip()
            stdout_text = (result.stdout or "").strip()
            combined = f"{stdout_text}\n{stderr_text}".strip().lower()
            if allow_nothing_to_commit and "nothing to commit" in combined:
                return result
            details = stderr_text or stdout_text or "(no output)"
            raise RuntimeError(f"{step_name} failed: {details}")

        return result

    def _get_commit_message_path(self) -> Path:
        base = Path(self.working_directory) if self.working_directory else Path.cwd()
        return base / self.COMMIT_MESSAGE_FILE

    def _relative_message_path(self, message_path: Path) -> str:
        base = Path(self.working_directory) if self.working_directory else Path.cwd()
        try:
            return message_path.relative_to(base).as_posix()
        except ValueError:
            return str(message_path)

    def _ensure_remote_config(self):
        """Ensure origin remote exists and matches configured URL when provided."""
        if self.git_remote:
            try:
                get_remote = subprocess.run(
                    ["git", "remote", "get-url", "origin"],
                    cwd=self.working_directory,
                    capture_output=True,
                    text=True,
                    check=False
                )
            except OSError as e:
                raise RuntimeError(f"Failed to check git remote origin: {e}") from e

            current_remote = (get_remote.stdout or "").strip()
            if get_remote.returncode != 0 and not current_remote:
                self._run_git_command(
                    ["remote", "add", "origin", self.git_remote],
                    step_name="git remote add origin"
                )
                return

            if get_remote.returncode != 0:
                details = (get_remote.stderr or "").strip() or "(no output)"
                raise RuntimeError(f"git remote get-url origin failed: {details}")

            if current_remote != self.git_remote:
                self._run_git_command(
                    ["remote", "set-url", "origin", self.git_remote],
                    step_name="git remote set-url origin"
                )
            return

        # No configured remote URL; still verify origin exists before pushing.
        self._run_git_command(
            ["remote", "get-url", "origin"],
            step_name="git remote get-url origin"
        )
