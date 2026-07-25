"""Data models used by the autonomous ProjectAgent layer."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
import uuid


class ExecutionState(str, Enum):
    QUEUED = "queued"
    PLANNING = "planning"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING_APPROVAL = "waiting_approval"


@dataclass
class TaskStep:
    description: str
    capability: str = "LLM"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    dependencies: list[str] = field(default_factory=list)
    verification_method: str = "expected_output"
    retry_strategy: str = "retry"
    status: ExecutionState = ExecutionState.QUEUED
    result: Any = None
    error: str | None = None
    retries: int = 0


@dataclass
class Goal:
    objective: str
    priority: int = 50
    dependencies: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: ExecutionState = ExecutionState.QUEUED
    steps: list[TaskStep] = field(default_factory=list)
    completed_tasks: list[str] = field(default_factory=list)
    failed_tasks: list[str] = field(default_factory=list)
    retry_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    execution_history: list[dict[str, Any]] = field(default_factory=list)
    category: str = "mixed"


@dataclass
class ProgressReport:
    goal_id: str | None
    state: ExecutionState | None
    completed_tasks: int
    remaining_tasks: int
    failed_tasks: int
    retries: int
    estimated_completion: str | None
    current_step: str | None = None

