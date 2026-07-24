"""Task execution engine for EchoDesk."""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from knowledge.knowledge import KnowledgeEngine
from internet.internet_engine import InternetEngine
from memory_engine.memory_engine import MemoryEngine
from vision.vision_engine import VisionEngine, VisionResult
from voice.voice_engine import VoiceEngine
from llm.engine import LLMEngine
from planner.planner import ExecutionPlan, ExecutionStatus, Task


@dataclass
class EngineResult:
    engine: str
    success: bool
    result: Any
    error: str | None = None


@dataclass
class ExecutionResult:
    plan: ExecutionPlan
    tasks: list[Task]
    status: str
    engines_used: list[str]
    final_response: str
    execution_time: float | None = None
    logs: list[str] = field(default_factory=list)

    def add_log(self, message: str) -> None:
        self.logs.append(message)


class TaskExecutor:
    """Execute plans by dispatching work to the required intelligence engines."""

    def __init__(
        self,
        memory_engine: MemoryEngine | None = None,
        knowledge_engine: KnowledgeEngine | None = None,
        internet_engine: InternetEngine | None = None,
        vision_engine: VisionEngine | None = None,
        voice_engine: VoiceEngine | None = None,
        llm_engine: LLMEngine | None = None,
    ) -> None:
        self.memory_engine = memory_engine or MemoryEngine()
        self.knowledge_engine = knowledge_engine or KnowledgeEngine()
        self.internet_engine = internet_engine or InternetEngine()
        self.vision_engine = vision_engine or VisionEngine()
        self.voice_engine = voice_engine or VoiceEngine()
        self.llm_engine = llm_engine or LLMEngine()

    def execute_plan(self, plan: ExecutionPlan, command: str) -> ExecutionResult:
        """Execute the provided plan by running tasks sequentially."""
        print("[Executor] Executing plan")
        tasks = plan.tasks if plan.tasks else self._tasks_from_capabilities(plan.required_capabilities)
        engines_used: list[str] = []
        final_outputs: list[str] = []
        result = ExecutionResult(plan=plan, tasks=tasks, status="PENDING", engines_used=[], final_response="")

        start_time = time.perf_counter()
        total_tasks = len(tasks)

        for index, task in enumerate(tasks, start=1):
            print(f"[Task {index}/{total_tasks}] Running {task.capability}")
            task.status = ExecutionStatus.RUNNING
            self._report_progress(tasks)

            execution = self._execute_task_with_retry(task, command)
            if execution["success"]:
                task.status = ExecutionStatus.SUCCESS
                task.result = execution.get("message")
                final_outputs.append(f"[{task.capability}] {task.result}")
            else:
                task.status = ExecutionStatus.FAILED
                task.error = execution.get("message")
                print(f"[Retry] Task failed: {task.error}")

                if self._task_blocks_remaining(task, tasks[index:]):
                    print("[Executor] Remaining tasks depend on failed task; halting execution.")
                    break

            engines_used.append(task.capability)
            self._report_progress(tasks)

        result.execution_time = time.perf_counter() - start_time
        result.status = self._build_result_status(tasks)
        result.engines_used = sorted(set(engines_used))
        result.final_response = self._merge_outputs(final_outputs)
        result.add_log(f"[Finished] Execution status: {result.status}")
        result.add_log(f"[Finished] Execution time: {result.execution_time:.2f}s")
        result.logs.extend(self._build_task_logs(tasks))
        return result

    def _execute_memory(self, command: str) -> str:
        result = self.memory_engine.process_command(command)
        if result is None:
            return "Memory engine did not understand the request."
        return result

    def _execute_task(self, task: Task, command: str) -> dict[str, Any]:
        capability = task.capability
        engine_name = capability.title()
        print(f"[Task] {task.description} -> {engine_name}")

        try:
            if capability == "Memory":
                return {"success": True, "message": self._execute_memory(command)}
            if capability == "Knowledge":
                return {"success": True, "message": self._execute_knowledge(command)}
            if capability == "Internet":
                return {"success": True, "message": self._execute_internet(command)}
            if capability == "Vision":
                return {"success": True, "message": self._execute_vision(command)}
            if capability == "Voice":
                return {"success": True, "message": self._execute_voice(command)}
            if capability == "LLM":
                return {"success": True, "message": self._execute_llm(command)}
            return {"success": False, "message": f"Capability {capability} is not supported yet."}
        except Exception as exc:
            return {"success": False, "message": str(exc)}

    def _execute_task_with_retry(self, task: Task, command: str) -> dict[str, Any]:
        result = self._execute_task(task, command)
        if result.get("success"):
            return result

        print("[Retry] Reattempting task once.")
        retry_result = self._execute_task(task, command)
        if retry_result.get("success"):
            return retry_result

        return retry_result

    def _tasks_from_capabilities(self, capabilities: list[str]) -> list[Task]:
        tasks = []
        for capability in capabilities:
            tasks.append(Task(id=str(uuid.uuid4()), description=f"Run {capability} capability.", capability=capability))
        return tasks

    def _build_result_status(self, tasks: list[Task]) -> str:
        if any(task.status == ExecutionStatus.FAILED for task in tasks):
            return "FAILED"
        if all(task.status == ExecutionStatus.SUCCESS for task in tasks):
            return "SUCCESS"
        if any(task.status == ExecutionStatus.RUNNING for task in tasks):
            return "RUNNING"
        return "PENDING"

    def _merge_outputs(self, outputs: list[str]) -> str:
        if not outputs:
            return "No task output was generated."
        return "\n".join(outputs)

    def _task_blocks_remaining(self, failed_task: Task, remaining_tasks: list[Task]) -> bool:
        # Current task model does not expose explicit dependencies, so
        # conservatively stop only when summary tasks follow an failed search.
        if failed_task.capability == "Internet":
            return any("summarize" in task.description.lower() for task in remaining_tasks)
        return False

    def _report_progress(self, tasks: list[Task]) -> None:
        completed = sum(1 for task in tasks if task.status == ExecutionStatus.SUCCESS)
        failed = sum(1 for task in tasks if task.status == ExecutionStatus.FAILED)
        running = sum(1 for task in tasks if task.status == ExecutionStatus.RUNNING)
        remaining = sum(1 for task in tasks if task.status == ExecutionStatus.PENDING)
        print(f"[Executor] Progress - Completed: {completed}, Running: {running}, Failed: {failed}, Remaining: {remaining}")

    def _build_task_logs(self, tasks: list[Task]) -> list[str]:
        logs = []
        for index, task in enumerate(tasks, start=1):
            logs.append(f"[Task] {index}/{len(tasks)} {task.description}: {task.status.value}")
            if task.result:
                logs.append(f"[Task] Result: {task.result}")
            if task.error:
                logs.append(f"[Task] Error: {task.error}")
        return logs

    def _execute_knowledge(self, command: str) -> str:
        result = self.knowledge_engine.search(command)
        if result is None:
            return "Knowledge engine did not produce an answer."
        return str(result)

    def _execute_internet(self, command: str) -> Any:
        result = self.internet_engine.search(command)
        if result is None:
            return {"status": "unavailable", "message": "Internet engine did not return a response."}
        return result

    def _execute_vision(self, command: str) -> str:
        result = self.vision_engine.analyze(command)
        if result is None:
            return "Vision engine did not return a result."

        if isinstance(result, VisionResult):
            details = [
                f"Summary: {result.summary}",
                f"Detected text length: {len(result.text)}",
                f"Average confidence: {result.confidence:.2f}",
            ]
            if result.ui_elements:
                details.append(f"Detected UI elements: {', '.join(result.ui_elements)}")
            if result.text:
                sample = result.text.strip().replace("\n", " ")
                details.append(f"Text preview: {sample[:250]}")
            return " | ".join(details)

        if isinstance(result, dict):
            return result.get("summary") or result.get("message") or str(result)

        return str(result)

    def _execute_voice(self, command: str) -> Any:
        if command.strip().lower() in ("listen", "wake", "microphone") or command.strip().lower().startswith("listen"):
            result = self.voice_engine.listen()
            if not isinstance(result, dict):
                return str(result)
            if not result.get("success"):
                return result.get("message", "Voice listen failed.")
            return result.get("transcript", "")

        result = self.voice_engine.speak(command)
        if not isinstance(result, dict):
            return str(result)
        if not result.get("success"):
            return result.get("message", "Voice engine did not return a result.")
        return result.get("spoken_text", command)

    def _execute_llm(self, command: str) -> str:
        context_entries = self.memory_engine.get_recent_context(limit=5)
        if context_entries:
            context_text = []
            for entry in context_entries:
                context_text.append(f"User: {entry.user}\nAssistant: {entry.assistant}")
            full_context = "\n---\n".join(context_text)
        else:
            full_context = None

        result = self.llm_engine.ask(command, context=full_context)
        if result is None:
            return "LLM engine did not return a response."
        return str(result)

    def _merge_responses(self, plan: ExecutionPlan, responses: dict[str, Any]) -> str:
        merged = []
        for capability, response in responses.items():
            merged.append(f"[{capability}] {response}")
        if not merged:
            return "No response could be generated."
        return "\n".join(str(item) for item in merged)
