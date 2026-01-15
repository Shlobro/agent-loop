"""Session manager for pause/resume functionality."""

import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from .exceptions import SessionError
from .state_machine import StateMachine


class SessionManager:
    """
    Manages session persistence for pause/resume functionality.
    Saves and loads session state to/from JSON file.
    """

    SESSION_FILE = "session_state.json"

    def __init__(self, working_directory: str = ""):
        self.working_dir = Path(working_directory) if working_directory else None
        self._session_file: Optional[Path] = None
        if self.working_dir:
            self._session_file = self.working_dir / self.SESSION_FILE

    def set_working_directory(self, working_directory: str):
        """Update the working directory for session storage."""
        self.working_dir = Path(working_directory)
        self._session_file = self.working_dir / self.SESSION_FILE

    def save_session(self, state_machine: StateMachine) -> bool:
        """
        Save current session state to file.
        Returns True if successful.
        """
        if not self._session_file:
            raise SessionError("Working directory not set")

        try:
            # Ensure directory exists
            self._session_file.parent.mkdir(parents=True, exist_ok=True)

            session_data = {
                "version": "1.0",
                "saved_at": datetime.now().isoformat(),
                "state": state_machine.to_dict()
            }

            # Write atomically
            temp_path = self._session_file.with_suffix(".tmp")
            temp_path.write_text(
                json.dumps(session_data, indent=2),
                encoding="utf-8"
            )
            temp_path.replace(self._session_file)
            return True

        except OSError as e:
            raise SessionError(f"Failed to save session: {e}")

    def load_session(self, state_machine: StateMachine) -> bool:
        """
        Load session state from file into state machine.
        Returns True if session was loaded successfully.
        """
        if not self._session_file:
            raise SessionError("Working directory not set")

        if not self._session_file.exists():
            return False

        try:
            content = self._session_file.read_text(encoding="utf-8")
            session_data = json.loads(content)

            # Validate version
            version = session_data.get("version", "1.0")
            if not version.startswith("1."):
                raise SessionError(f"Unsupported session version: {version}")

            # Restore state
            state_data = session_data.get("state", {})
            state_machine.from_dict(state_data)
            return True

        except json.JSONDecodeError as e:
            raise SessionError(f"Invalid session file format: {e}")
        except OSError as e:
            raise SessionError(f"Failed to load session: {e}")
        except KeyError as e:
            raise SessionError(f"Missing required session data: {e}")

    def has_saved_session(self) -> bool:
        """Check if a saved session exists."""
        if not self._session_file:
            return False
        return self._session_file.exists()

    def delete_session(self) -> bool:
        """Delete saved session file."""
        if not self._session_file:
            return False

        try:
            if self._session_file.exists():
                self._session_file.unlink()
            return True
        except OSError as e:
            raise SessionError(f"Failed to delete session: {e}")

    def get_session_info(self) -> Optional[Dict[str, Any]]:
        """
        Get basic info about saved session without loading it.
        Returns dict with 'saved_at' and 'phase' or None if no session.
        """
        if not self._session_file or not self._session_file.exists():
            return None

        try:
            content = self._session_file.read_text(encoding="utf-8")
            session_data = json.loads(content)
            return {
                "saved_at": session_data.get("saved_at"),
                "phase": session_data.get("state", {}).get("phase"),
                "iteration": session_data.get("state", {}).get("context", {}).get("current_iteration", 0)
            }
        except (json.JSONDecodeError, OSError):
            return None

    def get_session_file_path(self) -> Optional[str]:
        """Return the path to the session file."""
        if self._session_file:
            return str(self._session_file)
        return None
