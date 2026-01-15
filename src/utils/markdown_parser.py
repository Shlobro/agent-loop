"""Markdown task list parsing utilities."""

import re
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class Task:
    """Represents a single task from a markdown checklist."""
    text: str
    completed: bool
    line_number: int
    indent_level: int = 0


def parse_tasks(content: str) -> List[Task]:
    """
    Parse markdown task list into Task objects.
    Handles both `- [ ]` and `- [x]` formats.

    Args:
        content: The markdown content to parse

    Returns:
        List of Task objects
    """
    tasks = []
    lines = content.split('\n')

    # Pattern for markdown checkboxes: optional indent, dash, brackets with space or x
    pattern = re.compile(r'^(\s*)-\s*\[([ xX])\]\s*(.+)$')

    for line_num, line in enumerate(lines, 1):
        match = pattern.match(line)
        if match:
            indent, check, text = match.groups()
            completed = check.lower() == 'x'
            indent_level = len(indent)
            tasks.append(Task(
                text=text.strip(),
                completed=completed,
                line_number=line_num,
                indent_level=indent_level
            ))

    return tasks


def has_incomplete_tasks(content: str) -> bool:
    """Check if there are any incomplete tasks in the content."""
    tasks = parse_tasks(content)
    return any(not t.completed for t in tasks)


def count_tasks(content: str) -> Tuple[int, int]:
    """
    Count tasks in content.

    Returns:
        Tuple of (completed_count, total_count)
    """
    tasks = parse_tasks(content)
    completed = sum(1 for t in tasks if t.completed)
    return completed, len(tasks)


def get_incomplete_tasks(content: str) -> List[Task]:
    """Get all incomplete tasks."""
    tasks = parse_tasks(content)
    return [t for t in tasks if not t.completed]


def get_next_incomplete_task(content: str) -> Optional[Task]:
    """Get the first incomplete task, if any."""
    tasks = parse_tasks(content)
    for task in tasks:
        if not task.completed:
            return task
    return None


def get_completed_tasks(content: str) -> List[Task]:
    """Get all completed tasks."""
    tasks = parse_tasks(content)
    return [t for t in tasks if t.completed]


def mark_task_complete(content: str, task_text: str) -> str:
    """
    Mark a specific task as complete in the content.

    Args:
        content: The full markdown content
        task_text: The text of the task to mark complete

    Returns:
        Updated content with task marked complete
    """
    lines = content.split('\n')
    pattern = re.compile(r'^(\s*)-\s*\[ \]\s*' + re.escape(task_text) + r'\s*$')

    for i, line in enumerate(lines):
        if pattern.match(line):
            # Replace [ ] with [x]
            lines[i] = line.replace('[ ]', '[x]', 1)
            break

    return '\n'.join(lines)


def add_task(content: str, task_text: str, at_end: bool = True) -> str:
    """
    Add a new task to the content.

    Args:
        content: The full markdown content
        task_text: The text of the new task
        at_end: If True, add at end; if False, add at beginning of task list

    Returns:
        Updated content with new task
    """
    new_task = f"- [ ] {task_text}"
    lines = content.split('\n')

    if at_end:
        # Find the last task and add after it
        last_task_idx = -1
        for i, line in enumerate(lines):
            if re.match(r'^\s*-\s*\[[ xX]\]', line):
                last_task_idx = i

        if last_task_idx >= 0:
            lines.insert(last_task_idx + 1, new_task)
        else:
            lines.append(new_task)
    else:
        # Find the first task and add before it
        for i, line in enumerate(lines):
            if re.match(r'^\s*-\s*\[[ xX]\]', line):
                lines.insert(i, new_task)
                break
        else:
            lines.append(new_task)

    return '\n'.join(lines)


def remove_completed_tasks(content: str) -> str:
    """
    Remove all completed tasks from the content.

    Returns:
        Content with completed tasks removed
    """
    lines = content.split('\n')
    pattern = re.compile(r'^\s*-\s*\[[xX]\]')

    filtered_lines = [line for line in lines if not pattern.match(line)]
    return '\n'.join(filtered_lines)


def format_tasks_for_display(tasks: List[Task]) -> str:
    """
    Format tasks for display in the UI.

    Returns:
        Formatted string with task status indicators
    """
    lines = []
    for task in tasks:
        status = "✓" if task.completed else "○"
        indent = "  " * task.indent_level
        lines.append(f"{indent}{status} {task.text}")
    return '\n'.join(lines)


def get_task_summary(content: str) -> str:
    """
    Get a summary string of task completion status.

    Returns:
        String like "5/10 tasks completed"
    """
    completed, total = count_tasks(content)
    return f"{completed}/{total} tasks completed"


def extract_task_list_section(content: str) -> str:
    """
    Extract just the task list from content that may have other text.

    Returns:
        String containing only the task list lines
    """
    lines = content.split('\n')
    task_lines = []
    pattern = re.compile(r'^\s*-\s*\[[ xX]\]')

    for line in lines:
        if pattern.match(line):
            task_lines.append(line)

    return '\n'.join(task_lines)
