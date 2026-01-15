"""Qt signals for worker thread communication."""

from PySide6.QtCore import QObject, Signal


class WorkerSignals(QObject):
    """
    Defines signals available from a running worker thread.
    Must be a separate class since QRunnable cannot have signals directly.
    """

    # Lifecycle signals
    started = Signal()
    finished = Signal()
    error = Signal(tuple)  # (exception_type, exception_value, traceback_str)

    # Result signals
    result = Signal(object)  # Generic result data

    # Progress signals
    progress = Signal(int, int)  # (current, total)
    status = Signal(str)  # Status message

    # Log signals
    log = Signal(str, str)  # (message, level)

    # LLM-specific signals
    llm_output = Signal(str)  # Raw LLM output line
    llm_complete = Signal(str)  # Final LLM response

    # Phase-specific signals
    questions_ready = Signal(dict)  # Parsed questions JSON
    tasks_ready = Signal(str)  # tasks.md content
    task_completed = Signal(str)  # Completed task description
    review_complete = Signal(str, str)  # (review_type, result)
    iteration_complete = Signal(int)  # Iteration number
