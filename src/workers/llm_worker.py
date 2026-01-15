"""Generic LLM invocation worker."""

import subprocess
import sys
import threading
from typing import Optional

from .base_worker import BaseWorker
from ..llm.base_provider import BaseLLMProvider
from ..core.exceptions import LLMProcessError, LLMTimeoutError


class LLMWorker(BaseWorker):
    """
    Generic worker for invoking LLM commands via subprocess.
    Streams output in real-time and captures full response.
    """

    DEFAULT_TIMEOUT = 300  # 5 minutes

    def __init__(self, provider: BaseLLMProvider, prompt: str,
                 working_directory: Optional[str] = None,
                 timeout: int = DEFAULT_TIMEOUT,
                 model: Optional[str] = None):
        super().__init__()
        self.provider = provider
        self.prompt = prompt
        self.working_directory = working_directory
        self.timeout = timeout
        self.model = model
        self.process: Optional[subprocess.Popen] = None
        self._output_lines = []

    def execute(self) -> str:
        """Execute the LLM command and return the output."""
        command = self.provider.build_command(self.prompt, model=self.model)
        # Log the exact command being executed for debugging
        command_str = ' '.join(f'"{arg}"' if ' ' in arg or '"' in arg else arg for arg in command)
        self.log(f"Executing command: {command_str}", "info")
        model_info = f", Model: {self.model}" if self.model else ""
        self.log(f"Provider: {self.provider.display_name}{model_info}, Timeout: {self.timeout}s", "debug")

        # Check if provider uses stdin for prompt
        uses_stdin = getattr(self.provider, 'uses_stdin', False)
        stdin_data = None
        if uses_stdin:
            stdin_data = self.provider.get_stdin_prompt(self.prompt)
            self.log(f"Sending prompt via stdin ({len(stdin_data)} chars)", "info")
            # Show prompt preview
            preview = stdin_data[:200].replace('\n', ' | ')
            self.log(f"Prompt preview: {preview}{'...' if len(stdin_data) > 200 else ''}", "debug")
        else:
            self.log(f"Prompt passed via command args ({len(self.prompt)} chars)", "debug")

        try:
            # On Windows, if command doesn't already use cmd, we need shell=True
            # for npm-installed commands. But if provider uses cmd /c, no shell needed.
            use_shell = sys.platform == "win32" and command[0].lower() != "cmd"
            self.log(f"Process config: shell={use_shell}, cwd={self.working_directory}", "debug")

            self.process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE if uses_stdin else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=self.working_directory,
                bufsize=1,
                universal_newlines=True,
                shell=use_shell
            )
            self.log(f"Process started with PID: {self.process.pid}", "debug")

            self._output_lines = []

            # If using stdin, write prompt and close stdin
            if uses_stdin and stdin_data:
                self.log(f"Writing {len(stdin_data)} chars to stdin...", "debug")
                self.process.stdin.write(stdin_data)
                self.process.stdin.close()
                self.log(f"Stdin closed, waiting for output...", "debug")

            # Create a thread to read output (allows us to check for cancellation)
            output_thread = threading.Thread(target=self._read_output)
            output_thread.start()
            self.log(f"Output reader thread started", "debug")

            # Wait for process with timeout
            try:
                self.log(f"Waiting for process (timeout: {self.timeout}s)...", "debug")
                self.process.wait(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                self.log(f"Process timed out after {self.timeout}s, killing...", "warning")
                self.process.kill()
                self.process.wait()
                raise LLMTimeoutError(f"LLM process timed out after {self.timeout}s")

            output_thread.join(timeout=5)

            full_output = ''.join(self._output_lines)

            # Log process result for debugging
            self.log(f"Process exited with code {self.process.returncode}, output length: {len(full_output)} chars", "info")

            # Show output preview
            if full_output.strip():
                preview = full_output[:300].replace('\n', ' | ')
                self.log(f"Output preview: {preview}{'...' if len(full_output) > 300 else ''}", "debug")

            if self.process.returncode != 0 and not self._is_cancelled:
                raise LLMProcessError(
                    self.process.returncode,
                    f"Process exited with code {self.process.returncode}"
                )

            self.signals.llm_complete.emit(full_output)
            return full_output

        except FileNotFoundError:
            self.log(f"Command not found: {command[0]}", "error")
            self.log(f"Ensure {self.provider.display_name} is installed and in PATH", "error")
            raise LLMProcessError(
                -1,
                f"Command '{command[0]}' not found. Is {self.provider.display_name} installed?"
            )

    def _read_output(self):
        """Read output from process in a separate thread."""
        try:
            for line in iter(self.process.stdout.readline, ''):
                if self._is_cancelled:
                    break

                self._output_lines.append(line)
                self.signals.llm_output.emit(line.rstrip('\n\r'))

        except Exception:
            pass  # Process may have been killed

    def cancel(self):
        """Cancel the worker and terminate the process."""
        super().cancel()
        if self.process and self.process.poll() is None:
            self.log(f"Terminating LLM process (PID: {self.process.pid})...", "warning")
            try:
                self.process.terminate()
                # Give it a moment to terminate gracefully
                try:
                    self.process.wait(timeout=2)
                    self.log(f"Process terminated gracefully", "debug")
                except subprocess.TimeoutExpired:
                    self.log(f"Process did not terminate, force killing...", "warning")
                    self.process.kill()
                    self.log(f"Process killed", "debug")
            except Exception as e:
                self.log(f"Error during process termination: {e}", "debug")


class RetryingLLMWorker(LLMWorker):
    """
    LLM worker with automatic retry on transient failures.
    """

    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds

    def execute(self) -> str:
        """Execute with retry logic."""
        import time

        last_error = None
        self.log(f"RetryingLLMWorker: max {self.MAX_RETRIES} attempts, {self.RETRY_DELAY}s delay between retries", "debug")

        for attempt in range(1, self.MAX_RETRIES + 1):
            self.check_cancelled()
            self.log(f"Attempt {attempt}/{self.MAX_RETRIES} starting...", "debug")

            try:
                result = super().execute()
                if attempt > 1:
                    self.log(f"Succeeded on attempt {attempt}", "success")
                return result

            except LLMTimeoutError as e:
                self.log(f"Attempt {attempt}/{self.MAX_RETRIES}: Timeout after {self.timeout}s", "warning")
                last_error = e
                if attempt < self.MAX_RETRIES:
                    self.log(f"Waiting {self.RETRY_DELAY}s before retry...", "debug")
                    time.sleep(self.RETRY_DELAY)

            except LLMProcessError as e:
                # Some errors are not retryable
                if e.exit_code == -1:  # Command not found
                    self.log(f"Command not found - not retrying", "error")
                    raise
                self.log(f"Attempt {attempt}/{self.MAX_RETRIES}: Process error (exit code {e.exit_code})", "warning")
                last_error = e
                if attempt < self.MAX_RETRIES:
                    self.log(f"Waiting {self.RETRY_DELAY}s before retry...", "debug")
                    time.sleep(self.RETRY_DELAY)

        self.log(f"All {self.MAX_RETRIES} attempts failed", "error")
        raise last_error or LLMProcessError(-1, "Max retries exceeded")
