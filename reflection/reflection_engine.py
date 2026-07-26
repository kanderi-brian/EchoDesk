from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict, Optional

from planner.planner import ExecutionPlan
from executor.task_executor import ExecutionResult


class ReflectionEngine:
    def __init__(self, memory_engine: Optional[Any] = None):
        self.memory_engine = memory_engine
        self.last_feedback: Dict[str, Any] = {}

    def review_execution(
        self,
        command: str,
        plan: Optional[ExecutionPlan],
        result: ExecutionResult,
    ) -> Dict[str, Any]:
        success = getattr(result, "status", None) == "SUCCESS"
        failed_tasks = []
        failure_reasons = []

        if plan is not None:
            for task in plan.tasks:
                if getattr(task, "status", None) == "FAILED":
                    failed_tasks.append(task.description or task.tool)
                    error_message = getattr(task, "error", None)
                    if error_message:
                        failure_reasons.append(error_message)

        if not success and not failure_reasons:
            final_message = getattr(result, "final_response", None)
            if final_message:
                failure_reasons.append(str(final_message))

        retry_recommended = not success and bool(failed_tasks)
        replan_recommended = not success
        confidence = 0.9 if success else max(0.1, 0.5 - len(failure_reasons) * 0.05)

        summary = (
            f"Execution {'succeeded' if success else 'failed'} for '{command}'. "
            f"{len(failed_tasks)} failed tasks. "
            f"Confidence {confidence:.2f}."
        )

        feedback = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "command": command,
            "success": success,
            "failed_tasks": failed_tasks,
            "failure_reasons": failure_reasons,
            "retry_recommended": retry_recommended,
            "replan_recommended": replan_recommended,
            "confidence": confidence,
            "summary": summary,
        }

        self.last_feedback = feedback
        if self.memory_engine is not None:
            self.memory_engine.learn(
                command,
                capability="Reflection",
                success=success,
                response=summary,
                duration=0.0,
                engine="Reflection",
                record_command=False,
            )

        return feedback

    def detect_failures(self, feedback: Dict[str, Any]) -> bool:
        return not feedback.get("success", False)

    def suggest_retry(self, feedback: Dict[str, Any]) -> bool:
        return feedback.get("retry_recommended", False)

    def suggest_replan(self, feedback: Dict[str, Any]) -> bool:
        return feedback.get("replan_recommended", False)
