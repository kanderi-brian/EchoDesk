from __future__ import annotations
import time
from datetime import datetime
from typing import Any

from planner.planner import ExecutionPlan, PlanStep
from .executor import ExecutionStepExecutor
from .result import ExecutionResult


class ExecutionEngine:
    """Engine responsible for executing structured execution plans."""

    def __init__(self, step_executor: ExecutionStepExecutor | None = None) -> None:
        self.step_executor = step_executor or ExecutionStepExecutor()
        self._cancelled = False
        self._paused = False
        self._current_step_index = 0
        self._current_step: PlanStep | None = None
        self.current_plan: ExecutionPlan | None = None
        self.last_result: ExecutionResult | None = None
        self.execution_history: list[ExecutionResult] = []

    def execute_plan(self, plan: ExecutionPlan, max_retries: int = 1) -> ExecutionResult:
        """Execute an ExecutionPlan step by step and return an ExecutionResult."""
        result = ExecutionResult()
        result.started_at = datetime.now()
        self.current_plan = plan
        self.last_result = result

        if not isinstance(plan, ExecutionPlan):
            result.add_log("Invalid execution plan provided.")
            result.finalize(success=False, error="Invalid execution plan.")
            self.execution_history.append(result)
            return result

        result.add_log(f"Starting execution plan: {plan.goal}")

        for index, step in enumerate(plan.steps):
            if self._cancelled:
                result.add_log("Execution cancelled before step execution.")
                break

            while self._paused:
                result.add_log("Execution paused.")
                time.sleep(0.1)

            if step.status in ("completed", "skipped"):
                result.add_log(f"Skipping already completed step: {step.action}")
                continue

            self._current_step_index = index
            self._current_step = step
            step.status = "in_progress"
            result.add_log(f"Executing step {index + 1}/{len(plan.steps)}: {step.action}")

            step_start = time.perf_counter()
            step_result = self._execute_step_with_retries(step, max_retries)
            step.duration = time.perf_counter() - step_start
            step.result = step_result.get("message") or ""

            if step_result.get("success"):
                step.status = "completed"
                result.completed_steps += 1
                if step.retry_count > 0:
                    result.retry_attempts += step.retry_count
                    result.recovered_failures.append(f"{step.action} recovered after {step.retry_count} retry(ies).")
                    result.add_log(f"Step recovered after retries: {step.action}")
                else:
                    result.add_log(f"Step succeeded: {step.action}")
                continue

            step.status = "failed"
            result.failed_step = step
            result.error = step_result.get("message") or "Step failed."
            result.add_log(f"Step failed: {step.action}. Error: {result.error}")

            if step.optional:
                step.status = "skipped"
                result.add_log(f"Optional step failed; continuing execution: {step.action}")
                continue

            result.finalize(success=False, failed_step=step, error=result.error)
            self.execution_history.append(result)
            return result

        if self._cancelled:
            result.finalize(success=False, error="Execution cancelled.")
            self.execution_history.append(result)
            return result

        # Finalize timing before generating the summary.
        result.finished_at = datetime.now()
        if result.started_at is not None:
            result.execution_time = (result.finished_at - result.started_at).total_seconds()
        execution_summary = self._build_execution_summary(plan, result)
        result.finalize(success=True, output=execution_summary)
        self.execution_history.append(result)
        return result

    def _execute_step_with_retries(self, step: PlanStep, max_retries: int) -> dict[str, Any]:
        attempt = 0
        last_result: dict[str, Any] = {"success": False, "message": "No execution attempt made."}

        while attempt <= max_retries:
            attempt += 1
            step.retry_count = attempt - 1
            last_result = self.step_executor.execute_step(step)
            if last_result.get("success"):
                return last_result
            if attempt <= max_retries and self._is_recoverable_failure(last_result):
                time.sleep(0.1)
                continue
            return last_result
        return last_result

    def retry_step(self, step: PlanStep | None = None, max_retries: int = 1) -> dict[str, Any]:
        """Retry a single failed step up to the provided retry limit."""
        if step is None:
            step = self._current_step
        if step is None:
            return {"success": False, "message": "No current step available to retry."}
        return self._execute_step_with_retries(step, max_retries)

    def skip_current_step(self) -> dict[str, Any]:
        """Skip the current step and continue execution."""
        if self._current_step is None:
            return {"success": False, "message": "No current step available to skip."}

        self._current_step.status = "skipped"
        self._current_step.result = "Skipped by user request."
        return {"success": True, "message": f"Skipped step: {self._current_step.action}."}

    def _build_execution_summary(self, plan: ExecutionPlan, result: ExecutionResult) -> str:
        completed = [step.action for step in plan.steps if step.status == "completed"]
        skipped = [step.action for step in plan.steps if step.status == "skipped"]
        failed = [step.action for step in plan.steps if step.status == "failed"]
        lines = [f"Execution summary for '{plan.goal}':"]
        lines.append(f"Completed steps: {len(completed)}")
        if completed:
            lines.append(f"  - {', '.join(completed)}")
        lines.append(f"Skipped steps: {len(skipped)}")
        if skipped:
            lines.append(f"  - {', '.join(skipped)}")
        lines.append(f"Failed steps: {len(failed)}")
        if failed:
            lines.append(f"  - {', '.join(failed)}")
        if result.recovered_failures:
            lines.append("Recovered failures:")
            for recovered in result.recovered_failures:
                lines.append(f"  - {recovered}")
        lines.append(f"Execution duration: {result.execution_time:.2f}s" if result.execution_time is not None else "Execution duration: unknown")
        return "\n".join(lines)

    def _is_recoverable_failure(self, result: dict[str, Any]) -> bool:
        message = str(result.get("message", "")).lower()
        recoverable_phrases = ["temporary", "timeout", "connection", "unavailable", "transient", "try again", "failed to connect"]
        return any(phrase in message for phrase in recoverable_phrases)

    def pause_execution(self) -> None:
        """Pause the currently running execution."""
        self._paused = True

    def resume_execution(self) -> None:
        """Resume a paused execution."""
        self._paused = False

    def cancel_execution(self) -> None:
        """Cancel the current execution flow."""
        self._cancelled = True

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    @property
    def current_step(self) -> PlanStep | None:
        return self._current_step
