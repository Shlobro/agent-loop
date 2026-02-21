"""Worker for Phase 2: Task Planning."""

from typing import Dict

from .base_worker import BaseWorker
from .llm_worker import LLMWorker
from ..llm.base_provider import LLMProviderRegistry
from ..llm.prompt_templates import PromptTemplates
from ..core.file_manager import FileManager
from ..utils.markdown_parser import parse_tasks


class PlanningWorker(BaseWorker):
    """
    Phase 2 worker: Generates task list from the summarized description.
    """

    def __init__(self, description: str, answers: Dict[str, str],
                 qa_pairs: list = None,
                 provider_name: str = "claude",
                 research_provider_name: str = "claude",
                 working_directory: str = None,
                 model: str = None,
                 research_model: str = None):
        super().__init__()
        self.description = description
        self.answers = answers
        self.qa_pairs = qa_pairs or []
        self.provider_name = provider_name
        self.research_provider_name = research_provider_name
        self.working_directory = working_directory
        self.model = model
        self.research_model = research_model

    def execute(self):
        """Generate task list from the project description."""
        self.update_status("Planning Tasks")
        self.log(f"=== TASK PLANNING PHASE START ===", "phase")
        self.log(f"Working directory: {self.working_directory}", "info")
        self.description = self._resolve_planning_description()
        self.log(f"Project description: {self.description[:200]}{'...' if len(self.description) > 200 else ''}", "info")
        if self.qa_pairs:
            self.log(f"User provided {len(self.qa_pairs)} Q&A pairs", "info")
        else:
            self.log(f"User provided {len(self.answers)} answers to clarifying questions", "info")

        provider = LLMProviderRegistry.get(self.provider_name)
        self.log(f"Using LLM provider: {provider.display_name}", "info")

        # Generate tasks.md
        self._generate_tasks(provider)

        # Generate research.md after tasks so it can use the planned tasks
        self._generate_research()

        # Emit tasks only after research phase completes
        self.signals.tasks_ready.emit(self.tasks_content)

        self.log(f"=== TASK PLANNING PHASE END ===", "phase")
        return {
            "tasks_content": self.tasks_content,
            "task_count": self.task_count
        }

    def _resolve_planning_description(self) -> str:
        """Load the project description for planning."""
        if not self.working_directory:
            return self.description
        file_manager = FileManager(self.working_directory)
        try:
            project_description = file_manager.read_file("product-description.md")
        except Exception as exc:
            self.log(f"Failed to read product-description.md: {exc}", "warning")
            return self.description
        if project_description and project_description.strip():
            self.log("Loaded project description from product-description.md", "info")
            return project_description.strip()
        self.log("product-description.md missing or empty; using current description", "info")
        return self.description

    def _generate_tasks(self, provider):
        """Generate tasks.md by having the LLM write directly to it."""
        self.update_status("Planning Tasks")
        self.log("Generating task list...", "info")
        file_manager = None
        if self.working_directory:
            file_manager = FileManager(self.working_directory)
            file_manager.ensure_files_exist()
            file_manager.write_tasks("")
        else:
            self.log("No working directory set; tasks.md cannot be prepared", "warning")

        # Build prompt
        base_prompt = PromptTemplates.format_planning_prompt(
            self.description,
            self.answers,
            qa_pairs=self.qa_pairs,
            working_directory=self.working_directory or "."
        )
        prompt = provider.format_prompt(base_prompt, "freeform")
        self.log(f"Built planning prompt ({len(prompt)} chars)", "debug")

        # Log answers summary
        if self.qa_pairs:
            for i, qa in enumerate(self.qa_pairs[:5], 1):
                question = qa.get("question", "")[:50]
                answer = qa.get("answer", "")[:50]
                self.log(f"  Q{i}: {question}{'...' if len(qa.get('question', '')) > 50 else ''}", "debug")
                self.log(f"  A{i}: {answer}{'...' if len(qa.get('answer', '')) > 50 else ''}", "debug")
            if len(self.qa_pairs) > 5:
                self.log(f"  ... and {len(self.qa_pairs) - 5} more Q&A pairs", "debug")
        else:
            for q_id, answer in list(self.answers.items())[:5]:
                self.log(f"  {q_id}: {answer[:50]}{'...' if len(answer) > 50 else ''}", "debug")
            if len(self.answers) > 5:
                self.log(f"  ... and {len(self.answers) - 5} more answers", "debug")

        # Run LLM
        self.log(f"Calling {provider.display_name} for task planning...", "info")

        llm_worker = LLMWorker(
            provider=provider,
            prompt=prompt,
            working_directory=self.working_directory,
            model=self.model,
            debug_stage="task_planning"
        )

        # Forward LLM output signals
        llm_worker.signals.llm_output.connect(
            lambda line: self.signals.llm_output.emit(line)
        )

        llm_worker.run()

        if llm_worker._is_cancelled:
            self.log(f"LLM worker was cancelled", "warning")
            self.check_cancelled()

        output = ''.join(llm_worker._output_lines)
        if output.strip():
            self.log(f"LLM output received ({len(output)} chars)", "debug")
        else:
            self.log("LLM produced no output", "warning")

        tasks_content = ""
        if file_manager:
            if file_manager.tasks_file.exists():
                tasks_content = file_manager.read_tasks()
                self.log(f"Loaded tasks from {file_manager.tasks_file}", "success")
                self.log(f"Task file size: {len(tasks_content)} chars", "debug")
            else:
                self.log("tasks.md was not created by the LLM", "warning")

        tasks = parse_tasks(tasks_content)
        if not tasks:
            self.log("Warning: No tasks found in tasks.md", "warning")
        else:
            self.log(f"Created {len(tasks)} tasks", "success")
            for i, task in enumerate(tasks[:10], 1):
                status = "[ ]" if not task.completed else "[x]"
                task_text = task.text[:60]
                self.log(f"  {i}. {status} {task_text}{'...' if len(task.text) > 60 else ''}", "debug")
            if len(tasks) > 10:
                self.log(f"  ... and {len(tasks) - 10} more tasks", "debug")

        # Store for return
        self.tasks_content = tasks_content
        self.task_count = len(tasks)

    def _generate_research(self):
        """Generate research.md after task planning."""
        self.update_status("Researching Product")
        self.log("Generating research.md from product-description.md and tasks.md...", "info")

        if not self.working_directory:
            self.log("No working directory set; skipping research phase", "warning")
            return

        file_manager = FileManager(self.working_directory)
        file_manager.ensure_files_exist()
        file_manager.write_file("research.md", "")

        provider = LLMProviderRegistry.get(self.research_provider_name)
        self.log(f"Using research LLM provider: {provider.display_name}", "info")

        base_prompt = PromptTemplates.format_research_prompt(
            working_directory=self.working_directory or "."
        )
        prompt = provider.format_prompt(base_prompt, "freeform")
        self.log(f"Built research prompt ({len(prompt)} chars)", "debug")

        llm_worker = LLMWorker(
            provider=provider,
            prompt=prompt,
            working_directory=self.working_directory,
            model=self.research_model,
            debug_stage="research"
        )

        llm_worker.signals.llm_output.connect(
            lambda line: self.signals.llm_output.emit(line)
        )
        llm_worker.signals.log.connect(
            lambda msg, level: self.signals.log.emit(msg, level)
        )

        llm_worker.run()

        if llm_worker._is_cancelled:
            self.log("Research LLM worker was cancelled", "warning")
            self.check_cancelled()

        research_content = file_manager.read_file("research.md") or ""
        if research_content.strip():
            self.log(f"Loaded research.md ({len(research_content)} chars)", "success")
        else:
            self.log("research.md is empty after research phase", "warning")
