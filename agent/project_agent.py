"""Background autonomous orchestration built on EchoDesk's existing engines."""

from __future__ import annotations

from collections import deque
from datetime import datetime
from threading import Condition, RLock, Thread
from typing import Any, Callable

from executor.task_executor import TaskExecutor
from planner.planner import ExecutionPlan, PlannerEngine, Task
from verification.verification_engine import VerificationEngine
from .models import ExecutionState, Goal, ProgressReport, TaskStep


class ProjectAgent:
    """Queue, plan, execute, verify, and recover goals using existing engines."""

    RISKY_TERMS = ("delete", "remove file", "install", "system setting", "format", "unknown script")

    def __init__(
        self,
        planner: PlannerEngine | None = None,
        executor: TaskExecutor | None = None,
        verifier: VerificationEngine | None = None,
        memory_engine: Any | None = None,
        vision_engine: Any | None = None,
        retry_limit: int = 2,
        approval_callback: Callable[[Goal], bool] | None = None,
    ) -> None:
        self.planner = planner or PlannerEngine()
        self.executor = executor or TaskExecutor(memory_engine=memory_engine)
        self.verifier = verifier or VerificationEngine(getattr(self.executor, "_llm_engine", None))
        self.memory_engine = memory_engine
        self.vision_engine = vision_engine
        self.retry_limit = max(0, int(retry_limit))
        self.approval_callback = approval_callback
        self.goals: dict[str, Goal] = {}
        self._queue: deque[str] = deque()
        self._current_goal_id: str | None = None
        self._lock, self._condition = RLock(), Condition(RLock())
        self._worker: Thread | None = None
        self._stopping = False

    def classify_goal(self, objective: str) -> str:
        text = objective.casefold()
        coding = any(word in text for word in ("code", "test", "repository", "python", "bug", "implement"))
        desktop = any(word in text for word in ("folder", "desktop", "launch", "rename", "form", "application"))
        research = any(word in text for word in ("research", "search", "news", "internet", "compare"))
        return "mixed" if sum((coding, desktop, research)) > 1 else "coding" if coding else "desktop automation" if desktop else "research" if research else "mixed"

    def add_goal(self, objective: str, priority: int = 50, dependencies: list[str] | None = None, start: bool = False) -> Goal:
        if not isinstance(objective, str) or not objective.strip():
            raise ValueError("Goal objective must be a non-empty string.")
        goal = Goal(objective=objective.strip(), priority=int(priority), dependencies=list(dependencies or []))
        goal.category = self.classify_goal(goal.objective)
        with self._lock:
            self.goals[goal.id] = goal
            self._queue.append(goal.id)
        if start:
            self.start()
        return goal

    submit_goal = add_goal

    def remove_goal(self, goal_id: str) -> bool:
        with self._lock:
            if goal_id not in self.goals or self.goals[goal_id].status == ExecutionState.RUNNING:
                return False
            self.goals.pop(goal_id)
            self._queue = deque(item for item in self._queue if item != goal_id)
            return True

    def pause_goal(self, goal_id: str) -> bool:
        return self._set_state(goal_id, ExecutionState.PAUSED)

    def resume_goal(self, goal_id: str) -> bool:
        goal = self.goals.get(goal_id)
        if goal is None or goal.status not in (ExecutionState.PAUSED, ExecutionState.WAITING_APPROVAL):
            return False
        goal.status = ExecutionState.QUEUED
        goal.updated_at = datetime.now().isoformat()
        if goal_id not in self._queue:
            self._queue.appendleft(goal_id)
        return True

    def cancel_goal(self, goal_id: str) -> bool:
        return self._set_state(goal_id, ExecutionState.CANCELLED)

    def reorder_queue(self, goal_id: str, position: int) -> bool:
        with self._lock:
            if goal_id not in self._queue:
                return False
            self._queue.remove(goal_id)
            self._queue.insert(max(0, min(position, len(self._queue))), goal_id)
            return True

    def start(self) -> None:
        with self._condition:
            if self._worker and self._worker.is_alive():
                return
            self._stopping = False
            self._worker = Thread(target=self._worker_loop, name="EchoDeskProjectAgent", daemon=True)
            self._worker.start()
            self._condition.notify_all()

    def stop(self, timeout: float = 1.0) -> None:
        with self._condition:
            self._stopping = True
            self._condition.notify_all()
        if self._worker:
            self._worker.join(timeout)

    def run_next(self) -> Goal | None:
        with self._lock:
            goal = self._next_runnable_goal()
        return self.run_goal(goal.id) if goal else None

    def run_goal(self, goal_id: str) -> Goal:
        goal = self.goals[goal_id]
        if goal.status in (ExecutionState.CANCELLED, ExecutionState.COMPLETED):
            return goal
        if self._needs_approval(goal) and not self._approved(goal):
            return self._transition(goal, ExecutionState.WAITING_APPROVAL, "Awaiting approval for sensitive operation.")
        self._current_goal_id = goal.id
        if not goal.steps:
            self._plan_goal(goal)
        if not goal.steps:
            return self._transition(goal, ExecutionState.FAILED, "Planner produced no executable steps.")
        self._transition(goal, ExecutionState.RUNNING, "Goal execution started.")
        for step in goal.steps:
            if goal.status in (ExecutionState.CANCELLED, ExecutionState.PAUSED):
                break
            if not self._dependencies_satisfied(goal, step):
                continue
            if not self._run_step(goal, step):
                goal.failed_tasks.append(step.id)
                if step.retries > self.retry_limit:
                    self._transition(goal, ExecutionState.FAILED, f"Retry limit exceeded for {step.description}.")
                    break
        if goal.status == ExecutionState.RUNNING:
            self._transition(goal, ExecutionState.COMPLETED, "Goal completed and verified.")
        self._current_goal_id = None
        return goal

    def get_progress(self, goal_id: str | None = None) -> ProgressReport:
        goal = self.goals.get(goal_id or self._current_goal_id) if (goal_id or self._current_goal_id) else None
        if goal is None:
            return ProgressReport(None, None, 0, 0, 0, 0, None)
        done = len(goal.completed_tasks)
        return ProgressReport(goal.id, goal.status, done, max(0, len(goal.steps) - done), len(goal.failed_tasks), goal.retry_count, "complete" if goal.status == ExecutionState.COMPLETED else "pending", next((s.description for s in goal.steps if s.status == ExecutionState.QUEUED), None))

    def inspect_project(self, root: str = ".") -> dict[str, bool]:
        from pathlib import Path
        path = Path(root)
        return {"readme": (path / "README.md").exists(), "requirements": (path / "requirements.txt").exists(), "tests": (path / "tests").is_dir(), "git": (path / ".git").exists()}

    def _plan_goal(self, goal: Goal) -> None:
        self._transition(goal, ExecutionState.PLANNING, "Planning goal.")
        plan = self.planner.plan(goal.objective)
        if plan is None:
            plan = ExecutionPlan(goal=goal.objective, tasks=[Task(id="fallback", description=goal.objective, capability="LLM")], required_capabilities=["LLM"])
        source_tasks = plan.tasks or [Task(id=step.id, description=step.description, capability="LLM") for step in plan.steps]
        previous: str | None = None
        for task in source_tasks:
            verification = "internet_response" if task.capability.casefold() == "internet" else "expected_output"
            step = TaskStep(description=task.description, capability=task.capability, id=task.id, dependencies=[previous] if previous else [], verification_method=verification)
            goal.steps.append(step)
            previous = step.id

    def _run_step(self, goal: Goal, step: TaskStep) -> bool:
        step.status = ExecutionState.RUNNING
        if goal.category in ("desktop automation", "mixed") and self.vision_engine:
            try:
                scene = self.vision_engine.capture_scene(refresh=False)
                self._record(goal, step, "vision", f"Desktop scene prepared with {len(scene.elements)} elements.")
            except Exception as exc:
                self._record(goal, step, "vision", f"Desktop scene unavailable: {exc}")
        task = Task(id=step.id, description=step.description, capability=step.capability)
        plan = ExecutionPlan(goal=goal.objective, tasks=[task], required_capabilities=[step.capability])
        result = self.executor.execute_plan(plan, goal.objective)
        output = result.final_response
        verification = self.verifier.verify(step.verification_method, output, result.expected_result if hasattr(result, "expected_result") else None)
        step.result = output
        if result.status == "SUCCESS" and verification.success:
            step.status = ExecutionState.COMPLETED
            goal.completed_tasks.append(step.id)
            self._record(goal, step, "completed", verification.message)
            self._remember(goal, step, True)
            return True
        step.retries += 1
        goal.retry_count += 1
        step.status = ExecutionState.QUEUED if step.retries <= self.retry_limit else ExecutionState.FAILED
        step.error = verification.message
        self._record(goal, step, "retry", verification.message)
        self._remember(goal, step, False)
        return step.retries <= self.retry_limit and self._run_step(goal, step)

    def _next_runnable_goal(self) -> Goal | None:
        for goal_id in sorted(self._queue, key=lambda item: self.goals[item].priority):
            goal = self.goals[goal_id]
            if goal.status == ExecutionState.QUEUED and all(self.goals.get(dep) and self.goals[dep].status == ExecutionState.COMPLETED for dep in goal.dependencies):
                self._queue.remove(goal_id)
                return goal
        return None

    def _worker_loop(self) -> None:
        while not self._stopping:
            goal = self.run_next()
            if goal is None:
                with self._condition:
                    self._condition.wait(timeout=0.1)

    def _needs_approval(self, goal: Goal) -> bool:
        return any(term in goal.objective.casefold() for term in self.RISKY_TERMS)

    def _approved(self, goal: Goal) -> bool:
        return bool(self.approval_callback and self.approval_callback(goal))

    def _dependencies_satisfied(self, goal: Goal, step: TaskStep) -> bool:
        return all(dep in goal.completed_tasks for dep in step.dependencies)

    def _set_state(self, goal_id: str, state: ExecutionState) -> bool:
        goal = self.goals.get(goal_id)
        if goal is None or goal.status in (ExecutionState.COMPLETED, ExecutionState.CANCELLED):
            return False
        self._transition(goal, state, f"Goal {state.value}.")
        return True

    def _transition(self, goal: Goal, state: ExecutionState, message: str) -> Goal:
        goal.status = state
        goal.updated_at = datetime.now().isoformat()
        goal.execution_history.append({"timestamp": goal.updated_at, "state": state.value, "message": message})
        return goal

    def _record(self, goal: Goal, step: TaskStep, state: str, message: str) -> None:
        goal.execution_history.append({"timestamp": datetime.now().isoformat(), "step": step.id, "state": state, "message": message})

    def _remember(self, goal: Goal, step: TaskStep, success: bool) -> None:
        if self.memory_engine and hasattr(self.memory_engine, "learn"):
            self.memory_engine.learn(goal.objective, capability=step.capability, success=success, response=str(step.result), engine="ProjectAgent")
