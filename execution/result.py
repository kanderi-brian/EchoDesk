from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ExecutionResult:
    success: bool = False
    completed_steps: int = 0
    failed_step: Any = None
    error: str | None = None
    output: Any = None
    recovered_failures: list[str] = field(default_factory=list)
    retry_attempts: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    execution_time: float | None = None
    logs: list[str] = field(default_factory=list)

    def add_log(self, message: str) -> None:
        """Append a log entry to the execution result."""
        if message is None:
            message = ""
        self.logs.append(str(message))

    def finalize(self, output: Any = None, error: str | None = None, success: bool = False, failed_step: Any = None) -> None:
        self.output = output
        self.error = error
        self.success = success
        self.failed_step = failed_step
        self.finished_at = datetime.now()
        if self.started_at is not None:
            self.execution_time = (self.finished_at - self.started_at).total_seconds()
        else:
            self.execution_time = 0.0
