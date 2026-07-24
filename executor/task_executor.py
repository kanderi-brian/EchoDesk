"""Task execution engine for EchoDesk."""

import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import Any

from planner.planner import ExecutionPlan, ExecutionStatus, Task
from memory_engine.memory_engine import MemoryEngine

# Heavy engines are imported lazily inside their respective execution methods to
# reduce startup cost.


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
    """Execute plans by dispatching work to the required intelligence engines.

    Engines other than the memory engine are created lazily to improve startup
    performance in production.
    """

    def __init__(
        self,
        memory_engine: MemoryEngine | None = None,
        knowledge_engine: Any | None = None,
        internet_engine: Any | None = None,
        vision_engine: Any | None = None,
        voice_engine: Any | None = None,
        llm_engine: Any | None = None,
        plugin_manager: object | None = None,
        retry_limit: int = 2,
    ) -> None:
        self.logger = logging.getLogger("echodesk.executor")
        self.memory_engine = memory_engine or MemoryEngine()
        # keep references but allow lazy construction when None
        self._knowledge_engine = knowledge_engine
        self._internet_engine = internet_engine
        self._vision_engine = vision_engine
        self._voice_engine = voice_engine
        self._llm_engine = llm_engine
        # Plugin manager may be injected by EchoBrain; keep optional for backward compatibility
        self.plugin_manager = plugin_manager
        self.retry_limit = max(0, int(retry_limit))

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
            task_start = time.perf_counter()

            execution = self._execute_task_with_retry(task, command)
            task_duration = time.perf_counter() - task_start
            if execution["success"]:
                task.status = ExecutionStatus.SUCCESS
                task.result = execution.get("message")
                final_outputs.append(f"[{task.capability}] {task.result}")
                self._record_learning(command, task.capability, task.result, True, task_duration)
            else:
                task.status = ExecutionStatus.FAILED
                task.error = execution.get("message")
                print(f"[Retry] Task failed: {task.error}")
                self._record_learning(command, task.capability, task.error, False, task_duration)

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
        try:
            result = self.memory_engine.process_command(command)
            if result is None:
                return "Memory engine did not understand the request."
            return result
        except Exception as exc:
            self.logger.exception("Memory execution failed")
            return "Memory engine failed to process the command." 

    def _execute_task(self, task: Task, command: str) -> dict[str, Any]:
        capability = task.capability
        engine_name = capability.title()
        self.logger.debug("[Task] %s -> %s", task.description, engine_name)

        # If this task explicitly requests a Plugin capability, run the plugin and return.
        try:
            pm = getattr(self, "plugin_manager", None)
            if capability == "Plugin":
                if pm is None:
                    return {"success": False, "message": "No plugin manager available."}
                try:
                    registry = pm.get_registry()
                    handler = registry.find_handler(command)
                    if not handler:
                        return {"success": False, "message": "No plugin found to handle the command."}
                    try:
                        result = handler.execute(command)
                        if result is None:
                            return {"success": True, "message": ""}
                        return {"success": True, "message": str(result)}
                    except Exception as exc:
                        self.logger.exception("Plugin execution failed: %s", getattr(handler, "name", "?"))
                        return {"success": False, "message": f"Plugin {getattr(handler, 'name', '?')} execution failed: {exc}"}
                except Exception:
                    self.logger.exception("Plugin registry error during plugin capability execution")
                    return {"success": False, "message": "Plugin execution failed due to registry error."}

            # Otherwise, before builtin engines, ask plugin manager if any plugin wants to handle this exact command.
            if pm is not None:
                try:
                    registry = pm.get_registry()
                    handler = registry.find_handler(command)
                    if handler:
                        try:
                            result = handler.execute(command)
                            # normalize result to string where appropriate
                            if result is None:
                                return {"success": True, "message": ""}
                            if isinstance(result, (str, int, float)):
                                return {"success": True, "message": str(result)}
                            return {"success": True, "message": str(result)}
                        except Exception as exc:
                            self.logger.exception("Plugin handler failed")
                            return {"success": False, "message": f"Plugin {getattr(handler, 'name', '?')} execution failed: {exc}"}
                except Exception:
                    # plugin registry errors should not break execution
                    self.logger.debug("Plugin registry check failed, continuing to builtin engines")
                    pass

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
            self.logger.exception("Unexpected error during task execution")
            return {"success": False, "message": str(exc)}

    def _execute_task_with_retry(self, task: Task, command: str) -> dict[str, Any]:
        attempt = 0
        last_result: dict[str, Any] = {"success": False, "message": "Task was not executed."}

        while attempt <= self.retry_limit:
            result = self._execute_task(task, command)
            attempt += 1
            task.retry_count = attempt
            if result.get("success"):
                return result

            last_result = result
            if attempt > self.retry_limit:
                break

            print(f"[Retry] Reattempting task ({attempt}/{self.retry_limit})")

        return last_result

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
        if self._knowledge_engine is None:
            from knowledge.knowledge import KnowledgeEngine

            self._knowledge_engine = KnowledgeEngine()
        try:
            result = self._knowledge_engine.search(command)
            if result is None:
                return "Knowledge engine did not produce an answer."
            return str(result)
        except Exception:
            self.logger.exception("Knowledge execution failed")
            return "Knowledge engine failed."

    def _execute_internet(self, command: str) -> Any:
        if self._internet_engine is None:
            from internet.internet_engine import InternetEngine

            self._internet_engine = InternetEngine()
        try:
            result = self._internet_engine.search(command)
            if result is None:
                return {"status": "unavailable", "message": "Internet engine did not return a response."}
            return result
        except Exception:
            self.logger.exception("Internet execution failed")
            return {"status": "error", "message": "Internet engine failed."}

    def _execute_vision(self, command: str) -> str:
        if self._vision_engine is None:
            from vision.vision_engine import VisionEngine, VisionResult

            self._vision_engine = VisionEngine()
        try:
            result = self._vision_engine.analyze(command)
            if result is None:
                return "Vision engine did not return a result."

            # handle VisionResult-like object
            try:
                SummaryClass = type(result)
                if hasattr(result, "summary") and hasattr(result, "text"):
                    details = [f"Summary: {result.summary}", f"Detected text length: {len(result.text)}", f"Average confidence: {getattr(result, 'confidence', 0.0):.2f}"]
                    if getattr(result, "ui_elements", None):
                        details.append(f"Detected UI elements: {', '.join(result.ui_elements)}")
                    if getattr(result, "text", None):
                        sample = result.text.strip().replace("\n", " ")
                        details.append(f"Text preview: {sample[:250]}")
                    return " | ".join(details)
            except Exception:
                pass

            if isinstance(result, dict):
                return result.get("summary") or result.get("message") or str(result)

            return str(result)
        except Exception:
            self.logger.exception("Vision execution failed")
            return "Vision engine failed."

    def _execute_voice(self, command: str) -> Any:
        if self._voice_engine is None:
            from voice.voice_engine import VoiceEngine

            self._voice_engine = VoiceEngine()
        try:
            normalized = command.strip().lower()
            if normalized in ("listen", "wake", "microphone") or normalized.startswith("listen"):
                result = self._voice_engine.listen()
                if not isinstance(result, dict):
                    return str(result)
                if not result.get("success"):
                    return result.get("message", "Voice listen failed.")
                return result.get("transcript", "")

            result = self._voice_engine.speak(command)
            if not isinstance(result, dict):
                return str(result)
            if not result.get("success"):
                return result.get("message", "Voice engine did not return a result.")
            return result.get("spoken_text", command)
        except Exception:
            self.logger.exception("Voice execution failed")
            return "Voice engine failed."

    def _execute_llm(self, command: str) -> str:
        if self._llm_engine is None:
            from llm.engine import LLMEngine

            self._llm_engine = LLMEngine()
        try:
            print("[LLM] Preparing context...")
            self.logger.debug("Collecting memory context for LLM (limit=5)")
            context_entries = self.memory_engine.get_recent_context(limit=5)
            # Ensure at most 5 entries are used even if underlying memory engine returned more
            if isinstance(context_entries, list):
                context_entries = context_entries[:5]

            context_text = []
            if context_entries:
                for entry in context_entries:
                    # Use a compact representation and keep recent entries
                    user = getattr(entry, "user", "")
                    assistant = getattr(entry, "assistant", "")
                    context_text.append(f"User: {user}\nAssistant: {assistant}")

            full_context = "\n---\n".join(context_text) if context_text else None

            # enforce overall approximate context size limit (~4000 chars)
            if full_context:
                max_total = 4000
                prompt_len = len(command or "")
                # If too long, drop oldest entries until within limits
                while len(full_context) + prompt_len > max_total and "---" in full_context:
                    parts = full_context.split("\n---\n")
                    if len(parts) <= 1:
                        break
                    parts.pop(0)
                    full_context = "\n---\n".join(parts)

            # Now call the LLM provider with clear progress messages and timing
            print("[LLM] Sending request...")
            self.logger.debug("LLM prompt size (approx): %d", len(full_context or "") + len(command or ""))
            print("[LLM] Waiting for response...")
            t0 = time.perf_counter()
            result = self._llm_engine.ask(command, context=full_context)
            t1 = time.perf_counter()
            print("[LLM] Response received.")
            self.logger.info("LLM response time: %.3fs", (t1 - t0))
            self.logger.debug("LLM context length: %d, prompt length: %d", len(full_context or ""), len(command or ""))

            if result is None:
                return "LLM engine did not return a response."
            return str(result)
        except Exception:
            self.logger.exception("LLM execution failed")
            return "LLM engine failed."

    def _record_learning(self, command: str, capability: str, response: str, success: bool, duration: float | None) -> None:
        if self.memory_engine is None:
            return

        try:
            self.memory_engine.learn(
                command=command,
                capability=capability,
                success=success,
                response=response,
                duration=duration,
                engine=capability,
            )
        except Exception:
            pass

    def _merge_responses(self, plan: ExecutionPlan, responses: dict[str, Any]) -> str:
        merged = []
        for capability, response in responses.items():
            merged.append(f"[{capability}] {response}")
        if not merged:
            return "No response could be generated."
        return "\n".join(str(item) for item in merged)
