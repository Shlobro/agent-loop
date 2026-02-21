"""State machine for managing workflow phases."""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from PySide6.QtCore import QObject, Signal

from .debug_settings import default_debug_breakpoints, normalize_debug_breakpoints
from ..llm.prompt_templates import PromptTemplates, ReviewType

class Phase(Enum):
    """Main execution phases."""
    IDLE = auto()
    QUESTION_GENERATION = auto()
    AWAITING_ANSWERS = auto()
    TASK_PLANNING = auto()
    MAIN_EXECUTION = auto()
    DEBUG_REVIEW = auto()
    GIT_OPERATIONS = auto()
    AWAITING_GIT_APPROVAL = auto()
    COMPLETED = auto()
    PAUSED = auto()
    ERROR = auto()
    CANCELLED = auto()


class SubPhase(Enum):
    """Sub-phases for detailed tracking."""
    NONE = auto()
    # Question generation (batch)
    GENERATING_QUESTIONS = auto()  # Generating a batch of questions
    AWAITING_ANSWERS = auto()  # Waiting for user to answer the batch
    # Main execution
    READING_TASKS = auto()
    EXECUTING_TASK = auto()
    # Debug review
    ARCHITECTURE_REVIEW = auto()
    ARCHITECTURE_FIX = auto()
    EFFICIENCY_REVIEW = auto()
    EFFICIENCY_FIX = auto()
    ERROR_HANDLING_REVIEW = auto()
    ERROR_HANDLING_FIX = auto()
    SAFETY_REVIEW = auto()
    SAFETY_FIX = auto()
    TESTING_REVIEW = auto()
    TESTING_FIX = auto()
    DOCUMENTATION_REVIEW = auto()
    DOCUMENTATION_FIX = auto()
    UI_UX_REVIEW = auto()
    UI_UX_FIX = auto()
    # Git
    GIT_ADD = auto()
    GIT_COMMIT = auto()
    GIT_PUSH = auto()


@dataclass
class StateContext:
    """Context data passed through state transitions."""
    description: str = ""
    answers: Dict[str, str] = field(default_factory=dict)
    questions_json: Dict[str, Any] = field(default_factory=dict)
    tasks_content: str = ""
    current_iteration: int = 0
    max_iterations: int = 10
    debug_iterations: int = 1
    current_debug_iteration: int = 0
    current_review_type: str = ""
    review_types: List[str] = field(
        default_factory=lambda: [ReviewType.GENERAL.value]
    )
    run_unit_test_prep: bool = True
    tasks_per_iteration: int = 1
    error_message: Optional[str] = None
    stop_requested: bool = False
    pause_requested: bool = False
    working_directory: str = ""
    git_mode: str = "local"
    git_remote: str = ""
    # Iterative question generation
    max_questions: int = 5
    current_question_num: int = 0
    qa_pairs: List[Dict[str, str]] = field(default_factory=list)  # [{"question": ..., "answer": ...}]
    current_question_text: str = ""  # The current question being displayed
    current_question_options: List[str] = field(default_factory=list)  # Options for current question
    is_last_question_shown: bool = False  # True when showing the last question
    questions_answered: bool = False  # True when current batch has been answered
    debug_mode_enabled: bool = False
    debug_breakpoints: Dict[str, Dict[str, bool]] = field(default_factory=default_debug_breakpoints)
    show_llm_terminals: bool = True
    # LLM configuration per stage
    llm_config: Dict[str, str] = field(default_factory=lambda: {
        "question_gen": "codex",
        "description_molding": "claude",
        "research": "claude",
        "task_planning": "claude",
        "coder": "codex",
        "reviewer": "codex",
        "fixer": "claude",
        "unit_test_prep": "codex",
        "git_ops": "codex",
        "client_message_handler": "codex",
        "question_gen_model": "gpt-5.3-codex:low",
        "description_molding_model": "claude-sonnet-4-6",
        "research_model": "claude-sonnet-4-6",
        "task_planning_model": "claude-sonnet-4-6",
        "coder_model": "gpt-5.3-codex",
        "reviewer_model": "gpt-5.3-codex",
        "fixer_model": "claude-opus-4-6",
        "unit_test_prep_model": "gpt-5.3-codex",
        "git_ops_model": "gpt-5.3-codex:low",
        "client_message_handler_model": "gpt-5.3-codex:low",
    })
    # For pause/resume - track where we were
    paused_from_phase: Optional[Phase] = None
    paused_from_sub_phase: Optional[SubPhase] = None
    # Client messaging
    pending_client_messages: List[Dict[str, str]] = field(default_factory=list)
    # Each message: {"id": str, "content": str, "timestamp": str, "status": str}


class StateMachine(QObject):
    """
    Manages the phase transitions of the autonomous code generation workflow.
    Emits signals on phase changes for UI updates.
    """

    # Signals
    phase_changed = Signal(object, object)  # (Phase, SubPhase)
    context_updated = Signal(object)  # StateContext
    workflow_completed = Signal(bool)  # success

    # Valid transitions mapping
    # NOTE: GIT_OPERATIONS can transition back to MAIN_EXECUTION for per-task workflow
    TRANSITIONS = {
        Phase.IDLE: [Phase.QUESTION_GENERATION, Phase.MAIN_EXECUTION, Phase.CANCELLED],
        Phase.QUESTION_GENERATION: [Phase.AWAITING_ANSWERS, Phase.TASK_PLANNING, Phase.ERROR, Phase.CANCELLED, Phase.PAUSED],
        Phase.AWAITING_ANSWERS: [Phase.QUESTION_GENERATION, Phase.TASK_PLANNING, Phase.CANCELLED, Phase.PAUSED],
        Phase.TASK_PLANNING: [Phase.MAIN_EXECUTION, Phase.ERROR, Phase.CANCELLED, Phase.PAUSED],
        Phase.MAIN_EXECUTION: [Phase.DEBUG_REVIEW, Phase.GIT_OPERATIONS, Phase.COMPLETED, Phase.ERROR, Phase.CANCELLED, Phase.PAUSED],
        Phase.DEBUG_REVIEW: [Phase.GIT_OPERATIONS, Phase.ERROR, Phase.CANCELLED, Phase.PAUSED],
        Phase.GIT_OPERATIONS: [Phase.MAIN_EXECUTION, Phase.AWAITING_GIT_APPROVAL, Phase.COMPLETED, Phase.ERROR, Phase.CANCELLED, Phase.PAUSED],
        Phase.AWAITING_GIT_APPROVAL: [Phase.MAIN_EXECUTION, Phase.COMPLETED, Phase.CANCELLED],
        Phase.COMPLETED: [Phase.IDLE],
        Phase.PAUSED: [Phase.QUESTION_GENERATION, Phase.AWAITING_ANSWERS, Phase.TASK_PLANNING,
                       Phase.MAIN_EXECUTION, Phase.DEBUG_REVIEW, Phase.GIT_OPERATIONS, Phase.CANCELLED],
        Phase.ERROR: [Phase.IDLE],
        Phase.CANCELLED: [Phase.IDLE],
    }

    def __init__(self):
        super().__init__()
        self._phase = Phase.IDLE
        self._sub_phase = SubPhase.NONE
        self._context = StateContext()

    @property
    def phase(self) -> Phase:
        return self._phase

    @property
    def sub_phase(self) -> SubPhase:
        return self._sub_phase

    @property
    def context(self) -> StateContext:
        return self._context

    def can_transition_to(self, new_phase: Phase) -> bool:
        """Check if transition to new_phase is valid from current phase."""
        valid_targets = self.TRANSITIONS.get(self._phase, [])
        return new_phase in valid_targets

    def transition_to(self, new_phase: Phase,
                      sub_phase: SubPhase = SubPhase.NONE) -> bool:
        """
        Attempt to transition to a new phase.
        Returns True if successful, False if invalid transition.
        """
        if not self.can_transition_to(new_phase):
            return False

        # If pausing, remember where we were
        if new_phase == Phase.PAUSED:
            self._context.paused_from_phase = self._phase
            self._context.paused_from_sub_phase = self._sub_phase

        self._phase = new_phase
        self._sub_phase = sub_phase

        self.phase_changed.emit(self._phase, self._sub_phase)

        # Check for terminal states
        if new_phase in (Phase.COMPLETED, Phase.ERROR, Phase.CANCELLED):
            self.workflow_completed.emit(new_phase == Phase.COMPLETED)

        return True

    def resume(self) -> bool:
        """Resume from paused state to the previous phase."""
        if self._phase != Phase.PAUSED:
            return False

        if self._context.paused_from_phase is None:
            return False

        target_phase = self._context.paused_from_phase
        target_sub_phase = self._context.paused_from_sub_phase or SubPhase.NONE

        # Clear pause tracking
        self._context.paused_from_phase = None
        self._context.paused_from_sub_phase = None
        self._context.pause_requested = False

        self._phase = target_phase
        self._sub_phase = target_sub_phase

        self.phase_changed.emit(self._phase, self._sub_phase)
        return True

    def set_sub_phase(self, sub_phase: SubPhase):
        """Update sub-phase without changing main phase."""
        self._sub_phase = sub_phase
        self.phase_changed.emit(self._phase, self._sub_phase)

    def update_context(self, **kwargs):
        """Update context attributes."""
        for key, value in kwargs.items():
            if hasattr(self._context, key):
                setattr(self._context, key, value)
        self.context_updated.emit(self._context)

    def request_stop(self):
        """Request graceful stop at next iteration."""
        self._context.stop_requested = True
        self.context_updated.emit(self._context)

    def request_pause(self):
        """Request pause at next iteration."""
        self._context.pause_requested = True
        self.context_updated.emit(self._context)

    def reset(self):
        """Reset state machine to initial state."""
        self._phase = Phase.IDLE
        self._sub_phase = SubPhase.NONE
        self._context = StateContext()
        self.phase_changed.emit(self._phase, self._sub_phase)

    def set_error(self, message: str):
        """Transition to error state with message."""
        self._context.error_message = message
        self.transition_to(Phase.ERROR)

    def get_phase_display_name(self) -> str:
        """Get human-readable name for current phase."""
        if self._phase == Phase.AWAITING_ANSWERS and self._context.questions_answered:
            return "Ready to Continue"

        names = {
            Phase.IDLE: "Idle",
            Phase.QUESTION_GENERATION: "Generating Questions",
            Phase.AWAITING_ANSWERS: "Awaiting Answers",
            Phase.TASK_PLANNING: "Planning Tasks",
            Phase.MAIN_EXECUTION: "Executing Tasks",
            Phase.DEBUG_REVIEW: "Code Review",
            Phase.GIT_OPERATIONS: "Git Operations",
            Phase.AWAITING_GIT_APPROVAL: "Awaiting Git Approval",
            Phase.COMPLETED: "Completed",
            Phase.PAUSED: "Paused",
            Phase.ERROR: "Error",
            Phase.CANCELLED: "Cancelled",
        }
        return names.get(self._phase, str(self._phase))

    def get_sub_phase_display_name(self) -> str:
        """Get human-readable name for current sub-phase."""
        names = {
            SubPhase.NONE: "",
            SubPhase.GENERATING_QUESTIONS: "Generating Questions",
            SubPhase.AWAITING_ANSWERS: "Awaiting Answers",
            SubPhase.READING_TASKS: "Reading Tasks",
            SubPhase.EXECUTING_TASK: "Executing Task",
            SubPhase.ARCHITECTURE_REVIEW: "Architecture Review",
            SubPhase.ARCHITECTURE_FIX: "Fixing Architecture",
            SubPhase.EFFICIENCY_REVIEW: "Efficiency Review",
            SubPhase.EFFICIENCY_FIX: "Fixing Efficiency",
            SubPhase.ERROR_HANDLING_REVIEW: "Error Handling Review",
            SubPhase.ERROR_HANDLING_FIX: "Fixing Error Handling",
            SubPhase.SAFETY_REVIEW: "Safety Review",
            SubPhase.SAFETY_FIX: "Fixing Safety",
            SubPhase.TESTING_REVIEW: "Testing Review",
            SubPhase.TESTING_FIX: "Fixing Tests",
            SubPhase.DOCUMENTATION_REVIEW: "Documentation Review",
            SubPhase.DOCUMENTATION_FIX: "Fixing Documentation",
            SubPhase.UI_UX_REVIEW: "UI/UX Review",
            SubPhase.UI_UX_FIX: "Fixing UI/UX",
            SubPhase.GIT_ADD: "Git Add",
            SubPhase.GIT_COMMIT: "Git Commit",
            SubPhase.GIT_PUSH: "Git Push",
        }
        return names.get(self._sub_phase, str(self._sub_phase))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state machine state for persistence."""
        return {
            "phase": self._phase.name,
            "sub_phase": self._sub_phase.name,
            "context": {
                "description": self._context.description,
                "answers": self._context.answers,
                "questions_json": self._context.questions_json,
                "tasks_content": self._context.tasks_content,
                "current_iteration": self._context.current_iteration,
                "max_iterations": self._context.max_iterations,
                "debug_iterations": self._context.debug_iterations,
                "current_debug_iteration": self._context.current_debug_iteration,
                "current_review_type": self._context.current_review_type,
                "review_types": self._context.review_types,
                "run_unit_test_prep": self._context.run_unit_test_prep,
                "tasks_per_iteration": self._context.tasks_per_iteration,
                "working_directory": self._context.working_directory,
                "git_mode": self._context.git_mode,
                "git_remote": self._context.git_remote,
                "max_questions": self._context.max_questions,
                "current_question_num": self._context.current_question_num,
                "qa_pairs": self._context.qa_pairs,
                "current_question_text": self._context.current_question_text,
                "current_question_options": self._context.current_question_options,
                "is_last_question_shown": self._context.is_last_question_shown,
                "questions_answered": self._context.questions_answered,
                "debug_mode_enabled": self._context.debug_mode_enabled,
                "debug_breakpoints": self._context.debug_breakpoints,
                "show_llm_terminals": self._context.show_llm_terminals,
                "llm_config": self._context.llm_config,
                "pending_client_messages": self._context.pending_client_messages,
            }
        }

    def from_dict(self, data: Dict[str, Any]):
        """Restore state machine state from persistence."""
        self._phase = Phase[data["phase"]]
        self._sub_phase = SubPhase[data["sub_phase"]]

        ctx = data.get("context", {})
        self._context.description = ctx.get("description", "")
        self._context.answers = ctx.get("answers", {})
        self._context.questions_json = ctx.get("questions_json", {})
        self._context.tasks_content = ctx.get("tasks_content", "")
        self._context.current_iteration = ctx.get("current_iteration", 0)
        self._context.max_iterations = ctx.get("max_iterations", 10)
        self._context.debug_iterations = ctx.get("debug_iterations", 1)
        self._context.current_debug_iteration = ctx.get("current_debug_iteration", 0)
        self._context.current_review_type = ctx.get("current_review_type", "")
        self._context.review_types = ctx.get(
            "review_types",
            [ReviewType.GENERAL.value]
        )
        self._context.run_unit_test_prep = bool(ctx.get("run_unit_test_prep", True))
        self._context.tasks_per_iteration = ctx.get("tasks_per_iteration", 1)
        self._context.working_directory = ctx.get("working_directory", "")
        self._context.git_mode = ctx.get("git_mode", "local")
        self._context.git_remote = ctx.get("git_remote", "")
        self._context.max_questions = ctx.get("max_questions", 5)
        self._context.current_question_num = ctx.get("current_question_num", 0)
        self._context.qa_pairs = ctx.get("qa_pairs", [])
        self._context.current_question_text = ctx.get("current_question_text", "")
        self._context.current_question_options = ctx.get("current_question_options", [])
        self._context.is_last_question_shown = ctx.get("is_last_question_shown", False)
        self._context.questions_answered = ctx.get("questions_answered", False)
        self._context.debug_mode_enabled = bool(ctx.get("debug_mode_enabled", False))
        self._context.debug_breakpoints = normalize_debug_breakpoints(ctx.get("debug_breakpoints", {}))
        self._context.show_llm_terminals = bool(ctx.get("show_llm_terminals", True))
        loaded_llm_config = ctx.get("llm_config", {})
        merged_llm_config = dict(self._context.llm_config)
        if isinstance(loaded_llm_config, dict):
            merged_llm_config.update(loaded_llm_config)
        self._context.llm_config = merged_llm_config
        self._context.pending_client_messages = ctx.get("pending_client_messages", [])

        self.phase_changed.emit(self._phase, self._sub_phase)
        self.context_updated.emit(self._context)
