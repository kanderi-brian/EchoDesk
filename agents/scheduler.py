"""Dependency-aware scheduler for structured agent tasks."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from .models import AgentContext, AgentResult, AgentTask, TaskStatus
from .registry import AgentRegistry


class AgentScheduler:
    def __init__(self, registry: AgentRegistry, max_workers: int = 4) -> None:
        self.registry, self.max_workers = registry, max(1, max_workers)

    def run(self, tasks: list[AgentTask], context: AgentContext | None = None, parallel: bool = True) -> dict[str, AgentResult]:
        context, pending, results = context or AgentContext(), {task.id: task for task in tasks}, {}
        self._validate(tasks)
        while pending:
            ready = [task for task in pending.values() if all(dependency in results and results[dependency].success for dependency in task.dependencies)]
            if not ready:
                for task in pending.values(): task.status = TaskStatus.BLOCKED
                break
            if parallel and len(ready) > 1:
                with ThreadPoolExecutor(max_workers=min(self.max_workers, len(ready))) as pool:
                    futures = {pool.submit(self._run_one, task, context): task for task in ready}
                    for future in as_completed(futures): results[futures[future].id] = future.result()
            else:
                for task in ready: results[task.id] = self._run_one(task, context)
            for task in ready: pending.pop(task.id, None)
        return results

    def _run_one(self, task: AgentTask, context: AgentContext) -> AgentResult:
        agent = self.registry.get(task.assigned_agent)
        if agent is None:
            task.status = TaskStatus.FAILED
            return AgentResult(task.id, task.assigned_agent, False, error="Assigned agent is not registered.")
        task.status = TaskStatus.RUNNING
        result = agent.run(task, context)
        while not result.success and task.retries < task.max_retries:
            task.retries += 1
            agent.metrics["retries"] += 1
            result = agent.run(task, context)
        task.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
        return result

    @staticmethod
    def _validate(tasks: list[AgentTask]) -> None:
        ids = {task.id for task in tasks}
        dependency_map = {task.id: task.dependencies for task in tasks}
        for task in tasks:
            if task.id in task.dependencies or any(dep not in ids for dep in task.dependencies):
                raise ValueError("Tasks must only depend on distinct scheduled tasks.")
        visiting, visited = set(), set()
        def visit(task_id: str) -> None:
            if task_id in visiting:
                raise ValueError("Circular task dependencies are not allowed.")
            if task_id in visited:
                return
            visiting.add(task_id)
            for dependency in dependency_map[task_id]:
                visit(dependency)
            visiting.remove(task_id)
            visited.add(task_id)
        for task_id in dependency_map:
            visit(task_id)
