import threading
from datetime import datetime, timedelta
from typing import Any


class ContextEngine:
    """A thread-safe engine for conversational context management."""

    def __init__(self, max_turns: int = 20) -> None:
        """Initialize the ContextEngine.

        Args:
            max_turns: The maximum number of recent conversation turns to retain.
        """
        self._lock = threading.RLock()
        self.max_turns = max_turns if isinstance(max_turns, int) and max_turns > 0 else 20
        self._history: list[dict[str, Any]] = []
        self._goal: str | None = None
        self._completed_tasks: list[str] = []
        self._pending_tasks: list[str] = []
        self._active_application: str | None = None
        self._active_document: str | None = None
        self._active_project: str | None = None
        self._recent_files: list[str] = []
        self._current_execution_plan: Any | None = None
        self._previous_response: str | None = None
        self._last_updated = datetime.now()

    def _trim_history(self) -> None:
        max_messages = self.max_turns * 2
        while len(self._history) > max_messages:
            self._history.pop(0)

    def _update_timestamp(self) -> None:
        with self._lock:
            self._last_updated = datetime.now()

    def _record_message(self, role: str, message: str) -> dict[str, Any]:
        if not isinstance(message, str) or not message.strip():
            return self._error("Message must be a non-empty string.")

        with self._lock:
            self._history.append(
                {
                    "role": role,
                    "message": message.strip(),
                    "time": datetime.now().isoformat(),
                }
            )
            self._trim_history()
            self._update_timestamp()

        if role == "assistant":
            self._previous_response = message.strip()

        return self._success(
            f"add_{role}_message",
            f"Added {role} message to context.",
            result=message.strip(),
        )

    def add_user_message(self, message: str) -> dict[str, Any]:
        """Store the latest user message in context."""
        return self._record_message("user", message)

    def add_assistant_message(self, message: str) -> dict[str, Any]:
        """Store the latest assistant response in context."""
        return self._record_message("assistant", message)

    def set_active_project(self, project: str) -> dict[str, Any]:
        """Remember the current active project."""
        if not isinstance(project, str) or not project.strip():
            return self._error("Project name must be a non-empty string.")

        with self._lock:
            self._active_project = project.strip()
            self._update_timestamp()

        return self._success(
            "set_active_project",
            f"Active project set to {self._active_project}.",
            result=self._active_project,
        )

    def get_active_project(self) -> dict[str, Any]:
        """Return the current active project."""
        with self._lock:
            return self._success(
                "get_active_project",
                "Active project retrieved.",
                result=self._active_project,
            )

    def add_recent_file(self, file_path: str) -> dict[str, Any]:
        """Store a recently accessed file in context."""
        if not isinstance(file_path, str) or not file_path.strip():
            return self._error("File path must be a non-empty string.")

        normalized = file_path.strip()
        with self._lock:
            if normalized in self._recent_files:
                self._recent_files.remove(normalized)
            self._recent_files.insert(0, normalized)
            self._recent_files = self._recent_files[:10]
            self._update_timestamp()

        return self._success(
            "add_recent_file",
            f"Recent file added: {normalized}.",
            result=list(self._recent_files),
        )

    def get_recent_files(self) -> dict[str, Any]:
        """Return the most recently accessed files."""
        with self._lock:
            return self._success(
                "get_recent_files",
                "Recent files retrieved.",
                result=list(self._recent_files),
            )

    def set_execution_plan(self, plan: Any) -> dict[str, Any]:
        """Store the current execution plan in context."""
        with self._lock:
            self._current_execution_plan = plan
            self._update_timestamp()

        return self._success(
            "set_execution_plan",
            "Execution plan stored in context.",
            result=self._current_execution_plan,
        )

    def get_execution_plan(self) -> dict[str, Any]:
        """Return the current execution plan."""
        with self._lock:
            return self._success(
                "get_execution_plan",
                "Execution plan retrieved.",
                result=self._current_execution_plan,
            )

    def get_previous_assistant_response(self) -> dict[str, Any]:
        """Return the last assistant response stored in context."""
        with self._lock:
            return self._success(
                "get_previous_assistant_response",
                "Previous assistant response retrieved.",
                result=self._previous_response,
            )

    def expire_context(self, max_age_seconds: int = 3600) -> dict[str, Any]:
        """Expire temporary context after a period of inactivity."""
        if not isinstance(max_age_seconds, int) or max_age_seconds <= 0:
            return self._error("max_age_seconds must be a positive integer.")

        with self._lock:
            if datetime.now() - self._last_updated > timedelta(seconds=max_age_seconds):
                self._clear_temporary_context()
                return self._success(
                    "expire_context",
                    "Temporary context expired due to inactivity.",
                )

        return self._success(
            "expire_context",
            "Temporary context remains active.",
        )

    def _clear_temporary_context(self) -> None:
        self._history.clear()
        self._goal = None
        self._completed_tasks.clear()
        self._pending_tasks.clear()
        self._active_application = None
        self._active_document = None
        self._active_project = None
        self._recent_files.clear()
        self._current_execution_plan = None
        self._previous_response = None
        self._last_updated = datetime.now()

    def clear(self) -> dict[str, Any]:
        """Clear the current context state."""
        with self._lock:
            self._history.clear()
            self._goal = None
            self._completed_tasks.clear()
            self._pending_tasks.clear()
            self._active_application = None
            self._active_document = None
            self._active_project = None
            self._recent_files.clear()
            self._current_execution_plan = None
            self._previous_response = None
            self._update_timestamp()

        return self._success("clear", "Context cleared.")

    def set_goal(self, goal: str) -> dict[str, Any]:
        """Set the current user goal."""
        if not isinstance(goal, str) or not goal.strip():
            return self._error("Goal must be a non-empty string.")

        with self._lock:
            self._goal = goal.strip()
            self._update_timestamp()

        return self._success("set_goal", "Current goal updated.", result=self._goal)

    def get_goal(self) -> dict[str, Any]:
        """Return the current user goal."""
        with self._lock:
            return self._success("get_goal", "Current goal retrieved.", result=self._goal)

    def complete_task(self, task: str) -> dict[str, Any]:
        """Mark a pending task as completed."""
        if not isinstance(task, str) or not task.strip():
            return self._error("Task must be a non-empty string.")

        normalized = task.strip()
        with self._lock:
            if normalized in self._pending_tasks:
                self._pending_tasks.remove(normalized)
            if normalized not in self._completed_tasks:
                self._completed_tasks.append(normalized)
            self._update_timestamp()

        return self._success("complete_task", f"Task completed: {normalized}.", result=normalized)

    def add_pending_task(self, task: str) -> dict[str, Any]:
        """Add a task to the pending task list."""
        if not isinstance(task, str) or not task.strip():
            return self._error("Task must be a non-empty string.")

        normalized = task.strip()
        with self._lock:
            if normalized not in self._pending_tasks:
                self._pending_tasks.append(normalized)
            self._update_timestamp()

        return self._success("add_pending_task", f"Pending task added: {normalized}.", result=normalized)

    def get_pending_tasks(self) -> dict[str, Any]:
        """Return pending tasks."""
        with self._lock:
            return self._success("get_pending_tasks", "Pending tasks retrieved.", result=list(self._pending_tasks))

    def get_completed_tasks(self) -> dict[str, Any]:
        """Return completed tasks."""
        with self._lock:
            return self._success("get_completed_tasks", "Completed tasks retrieved.", result=list(self._completed_tasks))

    def set_active_application(self, name: str) -> dict[str, Any]:
        """Remember the name of the active application."""
        if not isinstance(name, str) or not name.strip():
            return self._error("Application name must be a non-empty string.")

        with self._lock:
            self._active_application = name.strip()
            self._update_timestamp()

        return self._success(
            "set_active_application",
            f"Active application set to {self._active_application}.",
            result=self._active_application,
        )

    def get_active_application(self) -> dict[str, Any]:
        """Return the current active application."""
        with self._lock:
            return self._success(
                "get_active_application",
                "Active application retrieved.",
                result=self._active_application,
            )

    def set_active_document(self, path: str) -> dict[str, Any]:
        """Remember the active document path."""
        if not isinstance(path, str) or not path.strip():
            return self._error("Document path must be a non-empty string.")

        with self._lock:
            self._active_document = path.strip()
            self._update_timestamp()

        return self._success(
            "set_active_document",
            f"Active document set to {self._active_document}.",
            result=self._active_document,
        )

    def get_active_document(self) -> dict[str, Any]:
        """Return the current active document."""
        with self._lock:
            return self._success(
                "get_active_document",
                "Active document retrieved.",
                result=self._active_document,
            )

    def get_recent_history(self) -> dict[str, Any]:
        """Return the most recent conversation history."""
        with self._lock:
            return self._success(
                "get_recent_history",
                "Recent history retrieved.",
                result=list(self._history),
            )

    def clear(self) -> dict[str, Any]:
        """Clear the current context state."""
        with self._lock:
            self._history.clear()
            self._goal = None
            self._completed_tasks.clear()
            self._pending_tasks.clear()
            self._active_application = None
            self._active_document = None
            self._active_project = None
            self._recent_files.clear()
            self._current_execution_plan = None
            self._previous_response = None
            self._update_timestamp()

        return self._success("clear", "Context cleared.")

    def _success(self, action: str, message: str, result: Any | None = None) -> dict[str, Any]:
        response = {"success": True, "action": action, "message": message}
        if result is not None:
            response["result"] = result
        return response

    def _error(self, message: str, details: str | None = None) -> dict[str, Any]:
        response = {"success": False, "action": "error", "message": message}
        if details is not None:
            response["details"] = details
        return response


_default_context_engine = ContextEngine()


def get_context_engine() -> ContextEngine:
    """Return the default shared ContextEngine instance."""
    return _default_context_engine
