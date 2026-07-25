"""Structured messages and shared state for EchoDesk collaboration."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from typing import Any
import uuid


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class AgentTask:
    description: str
    assigned_agent: str
    parent_goal: str = ""
    priority: int = 50
    dependencies: list[str] = field(default_factory=list)
    expected_output: str = ""
    verification_method: str = "expected_output"
    payload: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    retries: int = 0
    max_retries: int = 1
    status: TaskStatus = TaskStatus.PENDING

    def depends_on(self, task_id: str) -> bool:
        return task_id in self.dependencies


@dataclass
class AgentResult:
    task_id: str
    agent_name: str
    success: bool
    output: Any = None
    confidence: float = 0.0
    verification: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_seconds: float = 0.0
    learning_event: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentContext:
    """Thread-safe shared state; agents communicate only through this surface."""
    current_goal: str | None = None
    active_plan: Any = None
    completed_tasks: dict[str, AgentResult] = field(default_factory=dict)
    retrieved_memories: list[Any] = field(default_factory=list)
    research_results: list[Any] = field(default_factory=list)
    vision_state: Any = None
    execution_history: list[dict[str, Any]] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def record(self, event: str, **details: Any) -> None:
        with self._lock:
            self.execution_history.append({"timestamp": datetime.now(timezone.utc).isoformat(), "event": event, **details})

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self.data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self.data.get(key, default)

    def complete(self, result: AgentResult) -> None:
        with self._lock:
            self.completed_tasks[result.task_id] = result
        self.record("task_completed", task_id=result.task_id, agent=result.agent_name, success=result.success)
