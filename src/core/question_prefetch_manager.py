"""Manager for prefetching questions with a 2-question buffer."""

from typing import List, Dict, Optional, Callable
from collections import deque
from PySide6.QtCore import QObject, Signal, QThreadPool

from ..workers.question_worker import SingleQuestionWorker


class QuestionPrefetchManager(QObject):
    """
    Manages question generation with prefetching.

    Maintains a buffer of 2 questions ahead of the current one being shown:
    - At start: generates 3 questions (current + 2 ahead)
    - After each answer: starts generating the next question
    - On cancel: discards unanswered buffered questions
    """

    # Signals
    question_ready = Signal(dict)  # Emitted when a buffered question is available
    log_message = Signal(str, str)  # (message, level)

    PREFETCH_BUFFER_SIZE = 2  # Always keep 2 questions ahead

    def __init__(self, thread_pool: QThreadPool):
        super().__init__()
        self.thread_pool = thread_pool

        # Question queue: deque of {"question": str, "options": List[str]}
        self.question_queue = deque()

        # Track active workers generating questions
        self.active_workers = []

        # Configuration for question generation
        self.description = ""
        self.qa_pairs = []
        self.provider_name = "gemini"
        self.working_directory = None
        self.model = None
        self.max_questions = 20

        # Track state
        self.is_cancelled = False
        self.questions_generated_count = 0

    def initialize(self, description: str, provider_name: str,
                   working_directory: str, model: Optional[str],
                   max_questions: int):
        """Initialize the manager with configuration."""
        self.description = description
        self.provider_name = provider_name
        self.working_directory = working_directory
        self.model = model
        self.max_questions = max_questions
        self.qa_pairs = []
        self.question_queue.clear()
        self.active_workers.clear()
        self.is_cancelled = False
        self.questions_generated_count = 0

    def start_prefetching(self):
        """Start initial prefetch to maintain 2-question buffer."""
        # Calculate initial batch: always aim for the buffer size.
        initial_count = self.PREFETCH_BUFFER_SIZE

        self.log_message.emit(
            f"Starting initial prefetch of {initial_count} questions",
            "info"
        )

        # Use ensure_generating to maintain the buffer
        self.ensure_generating()

    def get_next_question(self) -> Optional[Dict]:
        """
        Get the next question from the buffer.
        Returns None if no question is ready.
        """
        if self.question_queue:
            return self.question_queue.popleft()
        return None

    def has_buffered_question(self) -> bool:
        """Check if there's a question ready in the buffer."""
        return len(self.question_queue) > 0

    def on_answer_submitted(self, question: str, answer: str):
        """
        Called when user submits an answer.
        Updates QA history and clears buffer since buffered questions have stale context.
        """
        self.qa_pairs.append({"question": question, "answer": answer})
        self.questions_generated_count += 1

        # Discard buffered questions - they were generated with old Q&A context
        discarded = len(self.question_queue)
        if discarded > 0:
            self.question_queue.clear()
            self.log_message.emit(
                f"Discarded {discarded} buffered questions (stale context after answer)",
                "debug"
            )

        # Cancel any active workers - they also have stale context
        if len(self.active_workers) > 0:
            workers_cancelled = len(self.active_workers)
            for worker in self.active_workers:
                worker.cancel()
            self.active_workers.clear()
            self.log_message.emit(
                f"Cancelled {workers_cancelled} active workers (stale context after answer)",
                "debug"
            )

        # Now generate fresh questions with updated Q&A context
        self.ensure_generating()

    def cancel(self):
        """Cancel all pending operations and clear the queue."""
        self.log_message.emit("Cancelling question prefetch manager", "info")
        self.is_cancelled = True

        # Cancel all active workers
        for worker in self.active_workers:
            worker.cancel()

        # Clear the queue
        discarded = len(self.question_queue)
        self.question_queue.clear()

        if discarded > 0:
            self.log_message.emit(f"Discarded {discarded} unanswered questions from buffer", "info")

    def get_pending_questions_count(self) -> int:
        """Get the number of questions in the buffer + being generated."""
        return len(self.question_queue) + len(self.active_workers)

    def ensure_generating(self):
        """
        Ensure that question generation is running to maintain the 2-question buffer.

        This is a public method that can be called when max_questions increases
        or when we need to ensure generation continues after a pause.

        It will start workers to ensure we always have 2 questions in the buffer
        (or fewer if we're close to max_questions).
        """
        if self.is_cancelled:
            return

        generation_limit = self._get_generation_limit()

        # Calculate how many questions we should have in total (answered + buffered + generating)
        total_count = self.questions_generated_count + len(self.question_queue) + len(self.active_workers)

        # Calculate how many more we can generate
        remaining = generation_limit - total_count

        if remaining <= 0:
            self.log_message.emit(
                f"Not generating - already at/beyond prefetch limit ({total_count}/{generation_limit})",
                "debug"
            )
            return

        # Calculate how many we need in the buffer (always try to maintain 2, but respect max)
        target_buffer = min(self.PREFETCH_BUFFER_SIZE, remaining)
        current_buffer = len(self.question_queue) + len(self.active_workers)
        needed = target_buffer - current_buffer

        # Start workers to fill the buffer
        for _ in range(max(0, needed)):
            self.log_message.emit(
                f"Starting question generation to maintain buffer (total: {total_count + 1}/{generation_limit})",
                "info"
            )
            self._start_generating_question()
            total_count += 1  # Account for the new worker we just started

    def _start_generating_question(self):
        """Start a background worker to generate the next question."""
        if self.is_cancelled:
            return

        generation_limit = self._get_generation_limit()

        # Check if we've hit the limit
        if self.questions_generated_count + len(self.question_queue) + len(self.active_workers) >= generation_limit:
            self.log_message.emit(
                "Not starting new question generation - at prefetch limit",
                "debug"
            )
            return

        worker = SingleQuestionWorker(
            description=self.description,
            previous_qa=list(self.qa_pairs),  # Copy current state
            provider_name=self.provider_name,
            working_directory=self.working_directory,
            model=self.model
        )

        # Connect signals
        worker.signals.single_question_ready.connect(
            lambda q: self._on_question_generated(worker, q)
        )
        worker.signals.error.connect(
            lambda msg: self._on_worker_error(worker, msg)
        )
        worker.signals.log.connect(
            lambda msg, level: self.log_message.emit(msg, level)
        )

        self.active_workers.append(worker)
        self.thread_pool.start(worker)

        self.log_message.emit(
            f"Started background question generation (active workers: {len(self.active_workers)})",
            "debug"
        )

    def _on_question_generated(self, worker: SingleQuestionWorker, question_data: dict):
        """Handle a successfully generated question."""
        if self.is_cancelled:
            return

        # Remove worker from active list
        if worker in self.active_workers:
            self.active_workers.remove(worker)

        # Add to queue
        self.question_queue.append(question_data)

        self.log_message.emit(
            f"Question generated and buffered (queue size: {len(self.question_queue)}, "
            f"active workers: {len(self.active_workers)})",
            "info"
        )

        # Emit signal that a question is ready
        self.question_ready.emit(question_data)

    def _on_worker_error(self, worker: SingleQuestionWorker, error_msg: str):
        """Handle worker error."""
        if worker in self.active_workers:
            self.active_workers.remove(worker)

        self.log_message.emit(
            f"Question generation failed: {error_msg}",
            "error"
        )

    def _get_generation_limit(self) -> int:
        """Allow prefetching extra questions beyond the current max."""
        return self.max_questions + self.PREFETCH_BUFFER_SIZE
