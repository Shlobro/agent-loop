"""Error context data structure for error recovery."""

from dataclasses import dataclass, field
from typing import List, Optional
from .state_machine import Phase, SubPhase, StateContext


@dataclass
class ErrorInfo:
    """
    Complete error context captured when a worker error occurs.
    Used by error recovery dialog to provide recovery options.
    """
    phase: Phase                           # Where error occurred
    sub_phase: SubPhase                    # Granular phase info
    error_summary: str                     # First 3 lines or 200 chars
    full_traceback: str                    # Complete traceback
    exception_type: str                    # Exception class name
    exception_value: str                   # Exception message
    recent_logs: List[str]                 # Last 50 log entries
    working_directory: str                 # Current working dir
    current_iteration: int                 # Loop iteration number
    max_iterations: int                    # Total iterations
    context_snapshot: Optional[StateContext] = None  # Pre-error state copy


class ErrorRecoveryTracker:
    """Prevent infinite retry loops."""

    def __init__(self):
        self.retry_counts: dict[tuple, int] = {}  # (phase, iteration) -> count
        self.max_retries_per_phase = 3

    def can_retry(self, phase: Phase, iteration: int) -> bool:
        """Check if retry is allowed for this phase/iteration."""
        key = (phase, iteration)
        return self.retry_counts.get(key, 0) < self.max_retries_per_phase

    def record_retry(self, phase: Phase, iteration: int):
        """Record a retry attempt."""
        key = (phase, iteration)
        self.retry_counts[key] = self.retry_counts.get(key, 0) + 1

    def reset_phase(self, phase: Phase, iteration: int):
        """Reset retry count for a phase/iteration."""
        key = (phase, iteration)
        self.retry_counts.pop(key, None)

    def get_retry_count(self, phase: Phase, iteration: int) -> int:
        """Get current retry count for phase/iteration."""
        key = (phase, iteration)
        return self.retry_counts.get(key, 0)
