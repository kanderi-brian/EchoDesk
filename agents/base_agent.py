"""Base class and metrics shared by all EchoDesk specialist agents."""
from __future__ import annotations

import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Any

from .models import AgentContext, AgentResult, AgentTask


class BaseAgent(ABC):
    name = "base"

    def __init__(self, **services: Any) -> None:
        self.services = services
        self.metrics = {"completed_tasks": 0, "failures": 0, "retries": 0, "total_duration": 0.0, "verification_successes": 0}
        self.logger = logging.getLogger(f"echodesk.agents.{self.name}")
        if not self.logger.handlers:
            os.makedirs("logs", exist_ok=True)
            handler = logging.FileHandler(os.path.join("logs", "agents.log"), encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def run(self, task: AgentTask, context: AgentContext) -> AgentResult:
        started = time.perf_counter()
        self.logger.info("assigned task=%s goal=%s", task.id, task.parent_goal)
        try:
            security = self.services.get("security_engine")
            if security is not None:
                decision = security.authorize(task.description, f"agent:{self.name}", "Specialist agent task")
                if not decision.allowed:
                    result = AgentResult(task.id, self.name, False, error=decision.reason)
                    context.complete(result)
                    return result
            result = self.execute(task, context)
            result.duration_seconds = time.perf_counter() - started
            self.metrics["completed_tasks" if result.success else "failures"] += 1
            self.metrics["total_duration"] += result.duration_seconds
            if result.verification.get("success"):
                self.metrics["verification_successes"] += 1
            result.learning_event = {"event": "agent_task", "agent": self.name, "task_id": task.id, "success": result.success, "strategy": task.description}
            context.complete(result)
            self._learn(result, task)
            self.logger.info("completed task=%s success=%s duration=%.3f", task.id, result.success, result.duration_seconds)
            return result
        except Exception as exc:
            duration = time.perf_counter() - started
            self.metrics["failures"] += 1
            self.metrics["total_duration"] += duration
            self.logger.exception("failed task=%s", task.id)
            result = AgentResult(task.id, self.name, False, error=str(exc), duration_seconds=duration)
            context.complete(result)
            return result

    @abstractmethod
    def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        """Execute a structured task without mutating another agent's internals."""

    def get_metrics(self) -> dict[str, float | int]:
        completed = self.metrics["completed_tasks"]
        return {**self.metrics, "average_execution_time": self.metrics["total_duration"] / completed if completed else 0.0, "verification_success_rate": self.metrics["verification_successes"] / completed if completed else 0.0}

    def _learn(self, result: AgentResult, task: AgentTask) -> None:
        learning = self.services.get("learning_engine")
        if learning:
            try:
                learning.record_outcome(task.description, result.success, duration=result.duration_seconds, confidence=result.confidence, verification_success=bool(result.verification.get("success")), retries=task.retries, failure=result.error or "")
            except Exception:
                self.logger.debug("structured learning hook unavailable", exc_info=True)
        memory = self.services.get("memory_engine")
        if memory and hasattr(memory, "learn"):
            try:
                memory.learn(task.description, capability=self.name, success=result.success, response=str(result.output), engine="MultiAgent")
            except Exception:
                self.logger.debug("learning hook unavailable", exc_info=True)
