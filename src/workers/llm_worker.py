"""Generic LLM invocation worker."""

import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

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
        self._live_terminal_process: Optional[subprocess.Popen] = None
        self._live_terminal_log_path: Optional[Path] = None
        self._live_terminal_lock = threading.Lock()
        self._output_lines = []

    def execute(self) -> str:
        """Execute the LLM command and return the output."""
        output_path = self._get_output_last_message_path()
        if output_path:
            try:
                output_path.unlink()
            except FileNotFoundError:
                pass
            except OSError as e:
                self.log(f"Failed to clear output file {output_path}: {e}", "warning")

        command = self.provider.build_command(
            self.prompt,
            model=self.model,
            working_directory=self.working_directory
        )
        # Log the exact command being executed for debugging
        command_str = ' '.join(f'"{arg}"' if ' ' in arg or '"' in arg else arg for arg in command)
        self.log(f"Executing command: {command_str}", "info")
        self._start_live_terminal(command_str)
        model_info = f", Model: {self.model}" if self.model else ""
        self.log(f"Provider: {self.provider.display_name}{model_info}, Timeout: {self.timeout}s", "debug")
        self._append_live_terminal_line(
            f"Provider: {self.provider.display_name}{model_info} | Timeout: {self.timeout}s"
        )

        # Check if provider uses stdin for prompt
        uses_stdin = getattr(self.provider, 'uses_stdin', False)
        stdin_data = None
        if uses_stdin:
            stdin_data = self.provider.get_stdin_prompt(self.prompt)
            self.log(f"Sending prompt via stdin ({len(stdin_data)} chars)", "info")
            self._append_live_terminal_line(f"Prompt transport: stdin ({len(stdin_data)} chars)")
            self._log_full_prompt(stdin_data, "stdin")
        else:
            self.log(f"Prompt passed via command args ({len(self.prompt)} chars)", "debug")
            self._append_live_terminal_line(f"Prompt transport: args ({len(self.prompt)} chars)")
            self._log_full_prompt(self.prompt, "args")

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
            self._append_live_terminal_line(f"Process PID: {self.process.pid}")

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
                self._append_live_terminal_line(f"Timed out after {self.timeout}s; terminating process.")
                self.process.kill()
                self.process.wait()
                raise LLMTimeoutError(f"LLM process timed out after {self.timeout}s")

            output_thread.join(timeout=5)

            full_output = ''.join(self._output_lines)
            if output_path and output_path.exists():
                try:
                    file_output = output_path.read_text(encoding="utf-8")
                except OSError as e:
                    self.log(f"Failed to read output file {output_path}: {e}", "warning")
                    file_output = ""
                if file_output.strip():
                    self._emit_output_lines(file_output)
                    self._output_lines.append(file_output)
                    if full_output and not full_output.endswith("\n"):
                        full_output += "\n"
                    full_output += file_output
                    self.log(f"Loaded output from {output_path}", "debug")

            # Log process result for debugging
            self.log(f"Process exited with code {self.process.returncode}, output length: {len(full_output)} chars", "info")
            self._append_live_terminal_line(
                f"Process exited with code {self.process.returncode}. Output length: {len(full_output)} chars."
            )

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
            self._append_live_terminal_line(f"Command not found: {command[0]}")
            raise LLMProcessError(
                -1,
                f"Command '{command[0]}' not found. Is {self.provider.display_name} installed?"
            )
        finally:
            self._stop_live_terminal()

    def _read_output(self):
        """Read output from process in a separate thread."""
        try:
            for line in iter(self.process.stdout.readline, ''):
                if self._is_cancelled:
                    break

                self._output_lines.append(line)
                self.signals.llm_output.emit(line.rstrip('\n\r'))
                self._append_live_terminal_line(line.rstrip('\n\r'))

        except Exception:
            pass  # Process may have been killed

    def _emit_output_lines(self, output_text: str):
        """Emit output text to the log viewer as LLM output lines."""
        for line in output_text.splitlines():
            self.signals.llm_output.emit(line)
            self._append_live_terminal_line(line)

    def _log_full_prompt(self, prompt_text: str, source: str):
        """Log the full prompt for visibility in the output log."""
        self.log(f"LLM prompt begin ({source})", "info")
        self._append_live_terminal_line(f"LLM prompt begin ({source})")
        if prompt_text:
            for line in prompt_text.splitlines():
                self.log(line, "info")
                self._append_live_terminal_line(line)
        else:
            self.log("(empty prompt)", "info")
            self._append_live_terminal_line("(empty prompt)")
        self.log(f"LLM prompt end ({source})", "info")
        self._append_live_terminal_line(f"LLM prompt end ({source})")

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
                    self._append_live_terminal_line("Process force-killed during cancellation.")
            except Exception as e:
                self.log(f"Error during process termination: {e}", "debug")
                self._append_live_terminal_line(f"Error during process termination: {e}")

    def _get_output_last_message_path(self) -> Optional[Path]:
        path_getter = getattr(self.provider, "get_output_last_message_path", None)
        if not callable(path_getter):
            return None
        output_path = path_getter(self.working_directory)
        if not output_path:
            return None
        return Path(output_path)

    def _start_live_terminal(self, command_str: str):
        """Open a live terminal window on Windows that tails this run's output log."""
        if sys.platform != "win32":
            return

        base_dir = Path(self.working_directory) if self.working_directory else Path.cwd()
        logs_dir = base_dir / ".agentharness" / "live-llm"
        try:
            logs_dir.mkdir(parents=True, exist_ok=True)
            log_path = logs_dir / f"llm_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}.log"
            log_path.write_text("", encoding="utf-8")
            self._live_terminal_log_path = log_path
        except OSError as e:
            self.log(f"Failed to initialize live terminal log: {e}", "warning")
            self._live_terminal_log_path = None
            return

        self._append_live_terminal_line("AgentHarness LLM Live Output")
        self._append_live_terminal_line(f"Start: {datetime.now().isoformat(timespec='seconds')}")
        self._append_live_terminal_line(f"CWD: {self.working_directory or str(base_dir)}")
        self._append_live_terminal_line(f"Command: {command_str}")
        self._append_live_terminal_line("")

        quoted_path = str(log_path).replace("'", "''")
        tail_script = (
            f"$p='{quoted_path}'; "
            "Get-Content -Path $p -Wait | ForEach-Object { "
            "if ($_ -eq '__AGENTHARNESS_LIVE_DONE__') { "
            "Write-Host ''; "
            "Write-Host 'LLM run complete. Close this terminal window when done reviewing.'; "
            "break "
            "}; "
            "Write-Host $_ "
            "}"
        )

        try:
            creation_flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
            self._live_terminal_process = subprocess.Popen(
                ["powershell", "-NoLogo", "-NoExit", "-Command", tail_script],
                creationflags=creation_flags
            )
            self.log(f"Live terminal opened for LLM run: {log_path}", "debug")
        except OSError as e:
            self.log(f"Failed to open live terminal window: {e}", "warning")
            self._live_terminal_process = None

    def _append_live_terminal_line(self, text: str):
        """Append one line to the live terminal log file if enabled."""
        if not self._live_terminal_log_path:
            return
        safe_text = text.rstrip("\n\r")
        try:
            with self._live_terminal_lock:
                with self._live_terminal_log_path.open("a", encoding="utf-8") as handle:
                    handle.write(f"{safe_text}\n")
        except OSError:
            pass

    def _stop_live_terminal(self):
        """Signal the live terminal tail process to exit."""
        if not self._live_terminal_log_path:
            return
        self._append_live_terminal_line(f"End: {datetime.now().isoformat(timespec='seconds')}")
        self._append_live_terminal_line("__AGENTHARNESS_LIVE_DONE__")


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
