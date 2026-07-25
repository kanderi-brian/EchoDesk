import datetime
import logging
import re
import time
from typing import Any, Optional

from brain.router import Router
from context.context import get_context_engine
from executor.task_executor import TaskExecutor
from memory.controller import MemoryController
from memory.memory import Memory
from memory_engine.memory_engine import MemoryEngine
from planner.planner import ExecutionPlan, PlannerEngine, PlanStep
from knowledge.knowledge import KnowledgeEngine
from goal_manager.goal_manager import GoalManager, GoalStatus
from runtime.agent_runtime import AgentRuntime
from reflection.reflection_engine import ReflectionEngine
from history.history_engine import HistoryEngine
from scheduler.scheduler import Scheduler
from agent.project_agent import ProjectAgent

# configuration and logging
from core.config import get_config
from core.logging_config import setup_logging


class EchoBrain:

    def __init__(
        self,
        memory_controller: Optional[MemoryController] = None,
        knowledge_engine: Optional[KnowledgeEngine] = None,
        internet_engine: Optional[Any] = None,
        llm_engine: Optional[Any] = None,
        desktop_controller: Optional[Any] = None,
        context_engine: Optional[Any] = None,
    ):
        self.router = Router()

        # Conversation history
        self.memory = Memory()

        # Long-term memory (dependency injection)
        self.memory_controller = memory_controller
        self.context_engine = context_engine or get_context_engine()

        # Optional external engines
        self.knowledge = knowledge_engine or KnowledgeEngine()
        self.internet_engine = internet_engine
        self.llm_engine = llm_engine
        self.desktop_controller = desktop_controller

        self.memory_engine = MemoryEngine()

        # Goal management and execution pipeline
        self.goal_manager = GoalManager()
        self.goal_manager.resume_interrupted_goals()
        self.reflection_engine = ReflectionEngine(memory_engine=self.memory_engine)
        self.history_engine = HistoryEngine()
        self.scheduler = Scheduler()
        self.agent_runtime = AgentRuntime(self)

        self.planner = PlannerEngine(learning_engine=self.memory_engine)
        # create executor but avoid forcing heavy engine instantiation (they'll be lazy-loaded)
        self.executor = TaskExecutor(
            memory_engine=self.memory_engine,
            knowledge_engine=self.knowledge if getattr(self, 'knowledge', None) is not None else None,
            internet_engine=self.internet_engine if getattr(self, 'internet_engine', None) is not None else None,
            vision_engine=None,
            voice_engine=None,
            llm_engine=self.llm_engine if getattr(self, 'llm_engine', None) is not None else None,
            plugin_manager=None,
            record_learning=False,
        )
        self.project_agent = ProjectAgent(
            planner=self.planner,
            executor=self.executor,
            memory_engine=self.memory_engine,
        )

        # Lazy-loaded vision modules
        self.capture = None
        self.reader = None
        self.analyzer = None

        # configure logging once per process
        setup_logging()
        self.logger = logging.getLogger("echodesk.brain")

        # Initialize PluginManager and load plugins (Phase 16.1 - Plugin Core)
        cfg = get_config()
        try:
            if cfg.get("plugins", {}).get("lazy_load"):
                self.plugin_manager = None
                self.logger.info("PluginManager lazy_load enabled; plugins will load on demand")
            else:
                from plugins.plugin_manager import PluginManager

                self.plugin_manager = PluginManager()
                loaded = self.plugin_manager.load_plugins()
                self.logger.info("[PluginManager] Loaded %d plugins", loaded)
                # Expose plugin manager to executor and planner
                try:
                    if hasattr(self, "executor") and self.executor is not None:
                        self.executor.plugin_manager = self.plugin_manager
                    if hasattr(self, "planner") and self.planner is not None:
                        try:
                            self.planner.set_plugin_registry(self.plugin_manager.get_registry())
                        except Exception:
                            pass
                except Exception:
                    self.logger.exception("Failed to attach plugin manager to subsystems")
        except Exception:
            # Plugin loading must not crash EchoBrain
            self.logger.exception("PluginManager failed to initialize")
            self.plugin_manager = None

    def reload_plugins(self) -> int:
        """Reload plugins at runtime via PluginManager."""
        if getattr(self, "plugin_manager", None) is None:
            return 0
        try:
            return self.plugin_manager.reload_plugins()
        except Exception:
            self.logger.exception("reload_plugins failed")
            return 0

    def shutdown_plugins(self) -> None:
        if getattr(self, "plugin_manager", None) is None:
            return
        try:
            self.plugin_manager.shutdown_plugins()
        except Exception:
            self.logger.exception("shutdown_plugins failed")

    def start_runtime(self) -> None:
        if getattr(self, "agent_runtime", None) is None:
            return
        self.agent_runtime.start()

    def stop_runtime(self) -> None:
        if getattr(self, "agent_runtime", None) is None:
            return
        self.agent_runtime.stop()

    def get_progress(self, goal_id: str | None = None) -> dict[str, Any]:
        """Return autonomous project-goal progress without changing legacy goal APIs."""
        report = self.project_agent.get_progress(goal_id)
        return {
            "current_goal": report.goal_id,
            "completed_tasks": report.completed_tasks,
            "remaining_tasks": report.remaining_tasks,
            "failed_tasks": report.failed_tasks,
            "retries": report.retries,
            "estimated_completion": report.estimated_completion,
            "execution_state": report.state.value if report.state else None,
            "current_step": report.current_step,
        }

    def submit_project_goal(self, objective: str, priority: int = 50, background: bool = True):
        """Queue a ProjectAgent goal while retaining existing GoalManager behavior."""
        return self.project_agent.add_goal(objective, priority=priority, start=background)

    def pause_runtime(self) -> None:
        if getattr(self, "agent_runtime", None) is None:
            return
        self.agent_runtime.pause()

    def resume_runtime(self) -> None:
        if getattr(self, "agent_runtime", None) is None:
            return
        self.agent_runtime.resume()

    def schedule_goal(
        self,
        goal_id: str,
        run_at: datetime.datetime,
        recurrence: str = "once",
    ) -> Any:
        if getattr(self, "scheduler", None) is None:
            return None
        return self.scheduler.schedule_goal(goal_id, run_at, recurrence)

    def cancel_schedule(self, schedule_id: str) -> bool:
        if getattr(self, "scheduler", None) is None:
            return False
        return self.scheduler.cancel_schedule(schedule_id)

    def get_schedules(self) -> list[dict[str, Any]]:
        if getattr(self, "scheduler", None) is None:
            return []
        return [entry.to_dict() for entry in self.scheduler.get_schedules()]

    def load_vision(self):

        if self.capture is None:
            self.logger.info("Lazy-loading Vision Engine")
            try:
                self.capture = ScreenCapture()
                self.reader = ScreenReader()
                self.analyzer = ScreenAnalyzer()
            except Exception:
                self.logger.exception("Failed to initialize Vision components")
                self.capture = None
                self.reader = None
                self.analyzer = None

    def _build_context_prompt(self, command: str, memory_context: str | None = None) -> str | None:
        if self.context_engine is None:
            return memory_context

        lines = []
        goal = self.context_engine.get_goal().get("result")
        active_app = self.context_engine.get_active_application().get("result")
        active_doc = self.context_engine.get_active_document().get("result")
        active_project = self.context_engine.get_active_project().get("result")
        pending_tasks = self.context_engine.get_pending_tasks().get("result")
        completed_tasks = self.context_engine.get_completed_tasks().get("result")
        recent_files = self.context_engine.get_recent_files().get("result")
        previous_response = self.context_engine.get_previous_assistant_response().get("result")

        if goal:
            lines.append(f"Current goal: {goal}")
        if active_app:
            lines.append(f"Active application: {active_app}")
        if active_project:
            lines.append(f"Active project: {active_project}")
        if active_doc:
            lines.append(f"Active document: {active_doc}")
        if pending_tasks:
            lines.append(f"Pending tasks: {pending_tasks}")
        if completed_tasks:
            lines.append(f"Completed tasks: {completed_tasks}")
        if recent_files:
            lines.append(f"Recent files: {recent_files}")
        if previous_response:
            lines.append(f"Previous assistant response: {previous_response}")

        history = self.context_engine.get_recent_history().get("result") or []
        if history:
            recent_history = history[-4:]
            formatted = []
            for message in recent_history:
                role = message.get("role")
                text = message.get("message")
                if role and text:
                    formatted.append(f"{role}: {text}")
            if formatted:
                lines.append("Recent conversation:\n" + "\n".join(formatted))

        if memory_context:
            lines.append(f"Relevant memories:\n{memory_context}")

        if not lines:
            return None

        return "\n\n".join(lines)

    def _get_memory_context(self, command: str) -> str | None:
        if self.memory_controller is None:
            return None

        try:
            result = self.memory_controller.search(command)
            if not result.get("success"):
                return None

            records = result.get("result") or []
            if not records:
                return None

            memory_lines = []
            for record in records[:5]:
                key = getattr(record, "key", None) or (record.get("key") if isinstance(record, dict) else None)
                value = getattr(record, "value", None) or (record.get("value") if isinstance(record, dict) else record)
                if key and value is not None:
                    memory_lines.append(f"{key}: {value}")
                else:
                    memory_lines.append(str(record))

            return "\n".join(memory_lines)
        except Exception:
            return None

    def _update_context_from_command(self, command: str, response: str) -> None:
        if self.context_engine is None:
            return

        normalized = command.strip().lower()
        if re.search(r"\b(open|launch|start)\s+(my\s+)?project\b", normalized):
            self.context_engine.set_active_project("current project")
        else:
            app_match = re.search(r"\b(?:open|launch|start)\s+(.+?)(?:\s|$)", normalized)
            if app_match:
                app_name = app_match.group(1).strip()
                if app_name:
                    self.context_engine.set_active_application(app_name)

    def _handle_memory_command(self, command: str):

        if self.memory_controller is None:
            return None

        text = command.strip()

        # Remember command
        remember = re.match(
            r"remember\s+(?:that\s+)?(.+?)\s+is\s+(.+)",
            text,
            re.IGNORECASE,
        )

        if remember:

            key = remember.group(1).strip()
            value = remember.group(2).strip()

            result = self.memory_controller.remember(key, value)

            if result.get("success"):
                return f"I'll remember that {key} is {value}."

            return result.get("message", "Unable to save memory.")

        # Generic remember command
        remember_plain = re.match(
            r"^(?:remember|please remember)\s+(.+)$",
            text,
            re.IGNORECASE,
        )

        if remember_plain:
            memo = remember_plain.group(1).strip()
            if memo:
                result = self.memory_controller.remember(memo, "remembered")
                if result.get("success"):
                    return f"I'll remember that {memo}."
                return result.get("message", "Unable to save memory.")

        # Recall captured facts by key or explicit query
        recall_all = re.match(
            r"^(?:what\s+do\s+you\s+remember|what\s+can\s+you\s+recall)\??$",
            text,
            re.IGNORECASE,
        )

        if recall_all:
            result = self.memory_controller.latest()
            if result.get("success"):
                records = result.get("result", {}).get("records", [])
                if not records:
                    return "I don't remember anything yet."
                remembered = [f"{item.get('key')}: {item.get('value')}" for item in records[:5]]
                return "I remember: " + "; ".join(remembered)
            return result.get("message", "Unable to retrieve memories.")

        recall = re.match(
            r"(?:what\s+is\s+my|what\s+are\s+my|where\s+is\s+my|recall)\s+(.+)",
            text,
            re.IGNORECASE,
        )

        if recall:

            key = recall.group(1).strip()

            result = self.memory_controller.recall(key)

            if result.get("success"):

                record = result.get("result")

                if record:

                    if hasattr(record, "value"):
                        return str(record.value)

                    return str(record)

            return "I don't remember that."

        # Search command
        search = re.match(
            r"(?:find|search|show).*(?:about|related to)\s+(.+)",
            text,
            re.IGNORECASE,
        )

        if search:

            query = search.group(1).strip()

            result = self.memory_controller.search(query)

            if result.get("success"):

                records = result.get("result", [])

                if not records:
                    return "I couldn't find any matching memories."

                lines = []

                for record in records:

                    key = getattr(record, "key", "Unknown")
                    value = getattr(record, "value", record)

                    lines.append(f"{key}: {value}")

                return "\n".join(lines)

            return result.get("message", "Search failed.")

        return None

    def _resolve_goal(self, identifier: str | None = None):
        if self.goal_manager is None:
            return None
        if identifier is None:
            return self.goal_manager.get_next_goal()
        return self.goal_manager.find_goal(identifier) or self.goal_manager.get_goal(identifier)

    def create_goal(
        self,
        title: str,
        description: str | None = None,
        priority: int = 50,
        dependencies: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        return self.goal_manager.create_goal(title, description, priority, dependencies, metadata)

    def remove_goal(self, goal_id: str) -> bool:
        return self.goal_manager.remove_goal(goal_id)

    def pause_goal(self, goal_id: str) -> bool:
        return self.goal_manager.pause_goal(goal_id)

    def resume_goal(self, goal_id: str) -> bool:
        return self.goal_manager.resume_goal(goal_id)

    def cancel_goal(self, goal_id: str) -> bool:
        return self.goal_manager.cancel_goal(goal_id)

    def complete_goal(self, goal_id: str) -> bool:
        return self.goal_manager.complete_goal(goal_id)

    def list_goals(self, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            goals = self.goal_manager.get_goals_by_status(status)
        else:
            goals = self.goal_manager.get_all_goals()
        return [goal.to_dict() for goal in goals]

    def goal_status(self, goal_id: str | None = None) -> dict[str, Any] | None:
        goal = self._resolve_goal(goal_id)
        return goal.to_dict() if goal is not None else None

    def history(self) -> dict[str, Any]:
        return {
            "goals": [goal.to_dict() for goal in self.goal_manager.get_all_goals()],
            "total_goals": len(self.goal_manager.get_all_goals()),
        }

    def run_goal(self, goal_id: str | None = None):
        goal = self._resolve_goal(goal_id)
        if goal is None:
            return "No active goal available to run."
        if goal.status == GoalStatus.Completed:
            return f"Goal '{goal.title}' is already completed."
        if goal.status == GoalStatus.Cancelled:
            return f"Goal '{goal.title}' was cancelled and cannot be resumed."

        if goal.status != GoalStatus.Running:
            self.goal_manager.resume_goal(goal.id)

        self.history_engine.record_goal_event(goal, "execution_started", f"Running goal '{goal.title}'.")

        plan = self.planner.plan(goal.description or goal.title)
        if plan is None:
            plan = ExecutionPlan(
                goal=goal.description or goal.title,
                steps=[
                    PlanStep(
                        id="fallback",
                        tool=goal.description or goal.title,
                        action="Generate response",
                        description="Fallback to LLM for the goal.",
                        expected_result="A response generated by the language model.",
                        engine="LLM",
                    )
                ],
                required_capabilities=["LLM"],
                reasoning="Fallback plan when no specific goal plan applies.",
                expected_result="Provide a helpful answer with the LLM.",
            )

        execution_result = self.executor.execute_plan(plan, goal.description or goal.title)
        if execution_result.status == "SUCCESS":
            self.goal_manager.complete_goal(goal.id)
            self.history_engine.record_goal_event(goal, "execution_completed", "Goal completed successfully.")
        else:
            goal.status = GoalStatus.Failed
            goal.updated_at = datetime.datetime.now().isoformat()
            self.goal_manager.save()
            self.history_engine.record_goal_event(goal, "execution_failed", execution_result.final_response)

        self.history_engine.record_plan(plan, execution_result.status, execution_result, goal.id)

        feedback = self.reflection_engine.review_execution(goal.description or goal.title, plan, execution_result)
        self.history_engine.record_reflection(feedback)
        try:
            self.planner.receive_feedback(feedback)
        except Exception:
            pass

        self.memory_engine.add_interaction(
            f"Goal: {goal.title}", execution_result.final_response, auto_flush=False
        )
        self.memory_engine.learn(
            command=goal.description or goal.title,
            capability="Goal",
            success=(execution_result.status == "SUCCESS"),
            response=execution_result.final_response,
            duration=execution_result.execution_time,
            engine="GoalManager",
        )

        return execution_result

    def _format_goal_list(self, goals: list[dict[str, Any]]) -> str:
        if not goals:
            return "No goals available."
        lines = []
        for goal in goals:
            lines.append(
                f"[{goal['status']}] {goal['title']} (priority={goal['priority']}, progress={goal['progress']}%)"
            )
        return "\n".join(lines)

    def _continue_goal(self) -> str:
        next_goal = self.goal_manager.get_next_goal()
        if next_goal is None:
            return "There is no active goal to continue right now."
        result = self.run_goal(next_goal.id)
        if isinstance(result, str):
            return result
        return result.final_response if hasattr(result, "final_response") else str(result)

    def _retry_failed_goal(self) -> str:
        failed_goals = self.goal_manager.get_goals_by_status("Failed")
        if not failed_goals:
            return "There are no failed goals to retry."
        latest = max(
            failed_goals,
            key=lambda goal: getattr(goal, "updated_at", getattr(goal, "created_at", "")),
        )
        latest.status = GoalStatus.Pending
        latest.updated_at = datetime.datetime.now().isoformat()
        self.goal_manager.save()
        result = self.run_goal(latest.id)
        if isinstance(result, str):
            return result
        return result.final_response if hasattr(result, "final_response") else str(result)

    def _handle_goal_command(self, command: str) -> str | dict[str, Any] | None:
        if self.goal_manager is None:
            return None

        normalized = command.strip().lower()

        create_match = re.match(
            r"^(?:create|add|set)\s+(?:a\s+)?goal(?:\s+to)?\s+(.+)$",
            command.strip(),
            re.IGNORECASE,
        )
        if create_match:
            title = create_match.group(1).strip()
            goal = self.goal_manager.create_goal(title, description=title)
            return f"Created goal: {goal.title}."

        if normalized in ("continue my work", "continue work", "resume my work", "continue", "continue goal"):
            return self._continue_goal()

        if normalized in ("pause all goals", "pause goals", "pause current goal"):
            active = self.goal_manager.get_active_goals()
            if not active:
                return "There are no active goals to pause."
            for goal in active:
                self.goal_manager.pause_goal(goal.id)
            return f"Paused {len(active)} active goal(s)."

        if normalized in ("cancel current goal", "cancel goal", "cancel work"):
            active = self.goal_manager.get_active_goals()
            if not active:
                return "There are no active goals to cancel."
            goal = active[0]
            self.goal_manager.cancel_goal(goal.id)
            return f"Cancelled goal: {goal.title}."

        if normalized in ("show active goals", "list active goals", "active goals"):
            return self._format_goal_list([g.to_dict() for g in self.goal_manager.get_active_goals()])

        if normalized in ("show completed goals", "list completed goals", "completed goals"):
            return self._format_goal_list([g.to_dict() for g in self.goal_manager.get_goals_by_status("Completed")])

        if normalized in ("what am i working on", "what am i working on?", "current goal"):
            active = self.goal_manager.get_active_goals()
            if not active:
                return "You have no active goals at the moment."
            return self._format_goal_list([g.to_dict() for g in active])

        if normalized in ("continue yesterday's work", "resume yesterday's work", "resume yesterday's work"):
            return self._continue_goal()

        if normalized in ("retry failed task", "retry failed goals", "retry failed goal"):
            return self._retry_failed_goal()

        if normalized in ("goal history", "show goal history"):
            return self._format_goal_list([g.to_dict() for g in self.goal_manager.get_all_goals()])

        return None

    def process(self, command: str, return_structured: bool = False) -> str | dict[str, Any]:
        """Process a user command through the unified intelligence runtime."""
        print("[EchoBrain] Received request")
        start_time = time.perf_counter()

        if self.context_engine is not None:
            try:
                self.context_engine.expire_context()
                self.context_engine.add_user_message(command)
            except Exception:
                pass

        # Support runtime plugin reload commands
        normalized_cmd = command.strip().lower()
        if normalized_cmd in ("reload plugins", "reload plugin", "reload plugin(s)", "refresh plugins", "refresh plugin"):
            count = self.reload_plugins()
            return f"Reloaded {count} plugins."

        goal_response = self._handle_goal_command(command)
        if goal_response is not None:
            plan = None
            result = None
            if isinstance(goal_response, str):
                final_response = goal_response
            elif hasattr(goal_response, "final_response"):
                final_response = goal_response.final_response
                result = goal_response
            elif isinstance(goal_response, dict):
                final_response = str(goal_response.get("result", goal_response.get("message", goal_response)))
            else:
                final_response = str(goal_response)
            engines_used = ["GoalManager"]
        else:
            route_result = None
            if self.router is not None:
                try:
                    route_result = self.router.route(command)
                except Exception:
                    route_result = None

            memory_response = self._handle_memory_command(command)
            if memory_response is not None:
                plan = None
                result = None
                final_response = memory_response
                engines_used = ["Memory"]
            elif isinstance(route_result, str) and route_result.lower() in {
                "greeting",
                "internet",
                "knowledge",
                "memory",
                "vision",
                "time",
                "screenshot",
                "voice",
            }:
                plan = None
                result = None
                final_response, engine_used = self._handle_legacy_route(route_result.lower(), command)
                engines_used = [engine_used]
            else:
                plan = self.planner.plan(command)

                if plan is None:
                    print("[Planner] No plan generated, falling back to LLM.")
                    plan = ExecutionPlan(
                        goal=command,
                        steps=[
                            PlanStep(
                                id="fallback",
                                tool=command,
                                action="Generate response",
                                description="Fallback to LLM for the user request.",
                                expected_result="A response generated by the language model.",
                                engine="LLM",
                            )
                        ],
                        required_capabilities=["LLM"],
                        reasoning="Fallback plan when no specific capability route applies.",
                        expected_result="Provide a helpful answer with the LLM.",
                    )
                else:
                    print(f"[Planner] Generated plan with capabilities: {plan.required_capabilities}")

                result = self.executor.execute_plan(plan, command)
                final_response = result.final_response
                engines_used = result.engines_used

        if self.context_engine is not None:
            try:
                self.context_engine.add_assistant_message(final_response)
                self._update_context_from_command(command, final_response)
            except Exception:
                pass

        self.memory.remember(command, final_response)
        self.memory_engine.add_interaction(command, final_response, auto_flush=False)
        self.memory_engine.learn(
            command,
            capability=(result.engines_used[0] if result else engines_used[0] if engines_used else None),
            success=(result.status == "SUCCESS" if result else bool(final_response)),
            response=final_response,
            duration=(result.execution_time if result else 0.0),
        )

        elapsed = time.perf_counter() - start_time
        print(f"[EchoBrain] Completed request in {elapsed:.3f}s")

        structured_response = {
            "request": command,
            "plan": plan,
            "engines_used": engines_used,
            "final_response": final_response,
            "details": result,
            "response": final_response,
        }

        if return_structured:
            return structured_response
        return final_response

    def _handle_legacy_route(self, route: str, command: str) -> tuple[str, str]:
        if route == "greeting":
            if self.llm_engine is not None:
                return self._llm_fallback(command), "LLM"
            return "Hello! I am EchoDesk. How can I help you?", "System"

        if route == "internet":
            if self.internet_engine is not None:
                try:
                    result = self.internet_engine.search(command)
                    if result is not None:
                        return str(result), "Internet"
                except Exception:
                    pass
            if self.llm_engine is not None:
                return self._llm_fallback(command), "LLM"
            return "Internet engine is unavailable.", "Internet"

        if route == "knowledge":
            if self.knowledge is not None:
                try:
                    result = self.knowledge.search(command)
                    if result is not None:
                        return str(result), "Knowledge"
                except Exception:
                    pass
            if self.llm_engine is not None:
                return self._llm_fallback(command), "LLM"
            return "Knowledge engine is unavailable.", "Knowledge"

        if route == "memory":
            memory_response = self._handle_memory_command(command)
            if memory_response is not None:
                return memory_response, "Memory"
            if self.llm_engine is not None:
                return self._llm_fallback(command), "LLM"
            return "I couldn't process the memory command.", "Memory"

        if route == "vision":
            self.load_vision()
            try:
                image = self.capture.take_screenshot()
                text = self.reader.read_image(image)
                result = self.analyzer.analyze(text)
                return result, "Vision"
            except Exception:
                if self.llm_engine is not None:
                    return self._llm_fallback(command), "LLM"
                return "Vision processing failed.", "Vision"

        if route == "voice":
            try:
                result = self.executor._execute_voice(command)
                return str(result), "Voice"
            except Exception:
                if self.llm_engine is not None:
                    return self._llm_fallback(command), "LLM"
                return "Voice engine is unavailable.", "Voice"

        if route == "time":
            return datetime.datetime.now().strftime("The current time is %H:%M:%S"), "System"

        if route == "screenshot":
            self.load_vision()
            try:
                image = self.capture.take_screenshot()
                return f"Screenshot saved to {image}", "System"
            except Exception:
                return "Screenshot capture failed.", "System"

        return "I don't understand that request yet.", "System"

    def _llm_fallback(self, command: str) -> str:
        if self.llm_engine is None:
            return (
                "I don't understand that request yet. "
                "Soon I'll be able to search AI or the web."
            )

        memory_context = self._get_memory_context(command)
        context_prompt = self._build_context_prompt(command, memory_context)

        try:
            answer = self.llm_engine.ask(command, context=context_prompt)
            if isinstance(answer, str) and answer.strip():
                return answer
            return "I'm sorry, I couldn't generate a response right now."
        except Exception as exc:
            self.logger.warning("LLM fallback failed: %s", exc)
            return "The AI assistant is unavailable right now. Please try again later."
