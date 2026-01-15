"""Custom exceptions for AgentHarness."""


class AgentHarnessError(Exception):
    """Base exception for all AgentHarness errors."""
    pass


class LLMError(AgentHarnessError):
    """Errors related to LLM invocation."""
    pass


class LLMTimeoutError(LLMError):
    """LLM process timed out."""
    pass


class LLMOutputParseError(LLMError):
    """Failed to parse LLM output."""
    pass


class LLMProcessError(LLMError):
    """LLM process returned non-zero exit code."""

    def __init__(self, exit_code: int, stderr: str = ""):
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(f"LLM process failed with exit code {exit_code}")


class FileOperationError(AgentHarnessError):
    """Errors related to file I/O."""
    pass


class TaskParseError(AgentHarnessError):
    """Failed to parse tasks.md."""
    pass


class StateTransitionError(AgentHarnessError):
    """Invalid state machine transition attempted."""
    pass


class WorkerCancelledError(AgentHarnessError):
    """Worker was cancelled before completion."""
    pass


class SessionError(AgentHarnessError):
    """Errors related to session persistence."""
    pass
