"""Chat history persistence for per-project conversation history."""

import json
from datetime import datetime
from pathlib import Path


class ChatHistoryManager:
    """Manages loading, saving, and formatting of chat history per project."""

    HISTORY_FILE = ".agentharness/chat-history.json"

    @staticmethod
    def load(working_directory: str) -> list:
        """Load chat history from working directory. Returns [] on missing/error."""
        if not working_directory:
            return []
        try:
            path = Path(working_directory) / ChatHistoryManager.HISTORY_FILE
            if not path.exists():
                return []
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
            return []
        except Exception:
            return []

    @staticmethod
    def save(working_directory: str, messages: list, limit: int = 50) -> None:
        """Trim to last `limit` entries and write atomically via .tmp file."""
        if not working_directory:
            return
        try:
            trimmed = messages[-limit:] if limit > 0 else []
            path = Path(working_directory) / ChatHistoryManager.HISTORY_FILE
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = path.with_suffix(".tmp")
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(trimmed, f, indent=2)
            tmp_path.replace(path)
        except Exception:
            pass

    @staticmethod
    def append_message(working_directory: str, role: str, content: str, limit: int = 50) -> None:
        """Append a single message to history and save."""
        if limit == 0 or not working_directory:
            return
        messages = ChatHistoryManager.load(working_directory)
        messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        ChatHistoryManager.save(working_directory, messages, limit=limit)

    @staticmethod
    def clear(working_directory: str) -> None:
        """Reset history file to empty list."""
        if not working_directory:
            return
        try:
            path = Path(working_directory) / ChatHistoryManager.HISTORY_FILE
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as f:
                json.dump([], f)
        except Exception:
            pass

    @staticmethod
    def format_for_prompt(messages: list) -> str:
        """Format chat history as a block for inclusion in LLM prompts."""
        if not messages:
            return ""
        lines = ["=== Recent Conversation History ==="]
        for entry in messages:
            role = entry.get("role", "user")
            content = entry.get("content", "")
            label = "User" if role == "user" else "Agent"
            lines.append(f"[{label}]: {content}")
        lines.append("=== End of Conversation History ===")
        return "\n".join(lines)
