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
    Phase 2 worker: Generates task list from description and answers.
    """

    def __init__(self, description: str, answers: Dict[str, str],
                 qa_pairs: list = None,
                 provider_name: str = "claude",
                 working_directory: str = None):
        super().__init__()
        self.description = description
        self.answers = answers
        self.qa_pairs = qa_pairs or []
        self.provider_name = provider_name
        self.working_directory = working_directory

    def execute(self):
        """Generate task list and save to tasks.md."""
        self.update_status("Creating task list...")
        self.log(f"=== TASK PLANNING PHASE START ===", "phase")
        self.log(f"Working directory: {self.working_directory}", "info")
        self.log(f"Project description: {self.description[:200]}{'...' if len(self.description) > 200 else ''}", "info")
        if self.qa_pairs:
            self.log(f"User provided {len(self.qa_pairs)} Q&A pairs", "info")
        else:
            self.log(f"User provided {len(self.answers)} answers to clarifying questions", "info")

        provider = LLMProviderRegistry.get(self.provider_name)
        self.log(f"Using LLM provider: {provider.display_name}", "info")

        # Build prompt
        base_prompt = PromptTemplates.format_planning_prompt(
            self.description,
            self.answers,
            qa_pairs=self.qa_pairs
        )
        prompt = provider.format_prompt(base_prompt, "markdown_tasks")
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
            working_directory=self.working_directory
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
        self.log(f"LLM output received ({len(output)} chars)", "debug")

        # Validate that we got tasks
        tasks = parse_tasks(output)
        self.log(f"Initial parse found {len(tasks)} tasks", "debug")

        if not tasks:
            self.log("No tasks found in initial parse, attempting extraction...", "debug")
            # Try to extract just the task lines from the output
            lines = output.split('\n')
            task_lines = [line for line in lines if line.strip().startswith('- [')]
            self.log(f"Found {len(task_lines)} lines starting with '- ['", "debug")
            if task_lines:
                output = '\n'.join(task_lines)
                tasks = parse_tasks(output)
                self.log(f"Extracted {len(tasks)} tasks after filtering", "debug")

        if not tasks:
            self.log("Warning: No tasks found in LLM output", "warning")
            self.log(f"Output preview: {output[:300]}{'...' if len(output) > 300 else ''}", "debug")
        else:
            self.log(f"Created {len(tasks)} tasks", "success")
            # Log task summary
            for i, task in enumerate(tasks[:10], 1):
                status = "[ ]" if not task.completed else "[x]"
                task_text = task.text[:60]
                self.log(f"  {i}. {status} {task_text}{'...' if len(task.text) > 60 else ''}", "debug")
            if len(tasks) > 10:
                self.log(f"  ... and {len(tasks) - 10} more tasks", "debug")

        # Ensure we have a proper header
        if not output.strip().startswith('#'):
            self.log("Adding '# Tasks' header to output", "debug")
            output = f"# Tasks\n\n{output}"

        # Save to file
        if self.working_directory:
            file_manager = FileManager(self.working_directory)
            file_manager.ensure_files_exist()
            file_manager.write_tasks(output)
            self.log(f"Saved tasks to {file_manager.tasks_file}", "info")
            self.log(f"Task file size: {len(output)} chars", "debug")

        self.log(f"=== TASK PLANNING PHASE END ===", "phase")
        self.signals.tasks_ready.emit(output)
        return {
            "tasks_content": output,
            "task_count": len(tasks)
        }
