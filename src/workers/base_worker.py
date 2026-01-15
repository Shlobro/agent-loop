"""Base worker class for threaded operations."""

import sys
import traceback
from PySide6.QtCore import QRunnable, Slot

from .signals import WorkerSignals
from ..core.exceptions import WorkerCancelledError


class BaseWorker(QRunnable):
    """
    Base class for all worker threads.
    Provides common error handling and signal infrastructure.
    """

    def __init__(self):
        super().__init__()
        self.signals = WorkerSignals()
        self._is_cancelled = False
        self._is_paused = False

    def cancel(self):
        """Request worker to stop at next safe point."""
        self._is_cancelled = True

    def pause(self):
        """Request worker to pause at next safe point."""
        self._is_paused = True

    def resume(self):
        """Resume from paused state."""
        self._is_paused = False

    def is_cancelled(self) -> bool:
        """Check if cancellation was requested."""
        return self._is_cancelled

    def is_paused(self) -> bool:
        """Check if pause was requested."""
        return self._is_paused

    def should_stop(self) -> bool:
        """Check if worker should stop (cancelled or paused)."""
        return self._is_cancelled or self._is_paused

    @Slot()
    def run(self):
        """
        Main execution method. Subclasses should override execute().
        This method handles error catching and signal emission.
        """
        try:
            self.signals.started.emit()
            result = self.execute()
            if not self._is_cancelled:
                self.signals.result.emit(result)
        except WorkerCancelledError:
            self.log("Worker cancelled", "warning")
        except Exception as e:
            exc_type, exc_value, exc_tb = sys.exc_info()
            tb_str = traceback.format_exc()
            self.signals.error.emit((exc_type, exc_value, tb_str))
            self.log(f"Error: {str(e)}", "error")
        finally:
            self.signals.finished.emit()

    def execute(self):
        """
        Override this method in subclasses to perform the actual work.
        Return value will be emitted via signals.result.
        """
        raise NotImplementedError("Subclasses must implement execute()")

    def log(self, message: str, level: str = "info"):
        """Convenience method for logging."""
        self.signals.log.emit(message, level)

    def update_status(self, status: str):
        """Convenience method for status updates."""
        self.signals.status.emit(status)

    def update_progress(self, current: int, total: int):
        """Convenience method for progress updates."""
        self.signals.progress.emit(current, total)

    def check_cancelled(self):
        """Check if cancelled and raise exception if so."""
        if self._is_cancelled:
            raise WorkerCancelledError("Worker was cancelled")

    def wait_if_paused(self):
        """
        Block while paused. Check periodically for cancel or resume.
        """
        import time
        while self._is_paused and not self._is_cancelled:
            time.sleep(0.1)

        if self._is_cancelled:
            raise WorkerCancelledError("Worker was cancelled while paused")
