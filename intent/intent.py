


import re
from typing import Any

from agent.agent import Agent
from agent.context import AgentContext
from tools.manager import ToolManager


class IntentEngine:

    GREETINGS = (
        "hello",
        "hi",
        "hey",
        "greetings",
        "good morning",
        "good afternoon",
        "good evening",
    )

    QUESTION_WORDS = (
        "who",
        "what",
        "where",
        "when",
        "why",
        "how",
        "which",
    )

    VISION_CUES = (
        "what do you see",
        "look at my screen",
        "read screen",
        "analyze screen",
        "vision",
        "screen",
    )

    INTERNET_CUES = (
        "search",
        "google",
        "wikipedia",
        "browse",
        "internet",
        "web",
        "news",
        "today",
        "happened",
        "weather",
        "forecast",
        "capital",
        "define",
        "information",
        "info",
        "latest",
        "stock",
        "price",
    )

    MEMORY_CUES = (
        "history",
        "remember",
        "recall",
        "memory",
        "forget",
        "delete",
        "remove",
        "update",
        "change",
    )

    SYSTEM_CUES = (
        "time",
        "screenshot",
        "status",
        "system",
    )

    def classify(self, command):
        if command is None:
            return "unknown"

        text = command.lower().strip()

        if not text:
            return "unknown"

        if self._is_greeting(text):
            return "greeting"

        if self._is_memory(text):
            return "memory"

        if self._is_vision(text):
            return "vision"

        if self._is_internet(text):
            return "internet"

        if self._is_system(text):
            return "system"

        if self._is_question(text):
            return "question"

        return "unknown"

    def _is_greeting(self, text):
        return any(text == phrase or text.startswith(f"{phrase} ") for phrase in self.GREETINGS)

    def _is_question(self, text):
        if text.endswith("?"):
            return True

        first_word = text.split()[0]
        return first_word in self.QUESTION_WORDS

    def _is_system(self, text):
        return any(phrase in text for phrase in self.SYSTEM_CUES)

    def _is_vision(self, text):
        return any(phrase in text for phrase in self.VISION_CUES)

    def _is_internet(self, text):
        return any(phrase in text for phrase in self.INTERNET_CUES)

    def _is_memory(self, text):
        return any(phrase in text for phrase in self.MEMORY_CUES)


class TaskExecutor:

    def __init__(self, intent_engine=None):
        self.intent_engine = intent_engine or IntentEngine()
        self.tool_manager = ToolManager()
        self.tool_manager.register_default_tools()
        self.agent_engine = self.tool_manager.get_tool("AgentEngine")
        self.agent = Agent()
        self.last_decision = None

    def execute(self, command):
        normalized = command.lower().strip() if command else ""

        if command:
            self.tool_manager.execute("ContextEngine", "add_user_message", command)
            if normalized not in ("continue", "resume", "cancel", "cancel execution", "retry", "skip", "history", "time", "screenshot"):
                self.tool_manager.execute("ContextEngine", "set_goal", command)

        if normalized == "history":
            return "history"

        if normalized == "screenshot":
            return "screenshot"

        if normalized in ("continue", "resume"):
            return "resume_execution"

        if normalized in ("cancel", "cancel execution"):
            return "cancel_execution"

        if normalized.startswith("retry"):
            return "retry_step"

        if normalized.startswith("skip"):
            return "skip_step"

        if (
            normalized == "time"
            or re.search(r"\bwhat time\b", normalized)
            or re.search(r"\btime is it\b", normalized)
            or normalized.startswith("current time")
            or normalized.startswith("local time")
        ):
            return "time"

        category = self.intent_engine.classify(command)
        planner_result = self.tool_manager.execute("PlannerEngine", "plan", command)
        plan = None
        if planner_result.get("success"):
            plan = planner_result.get("result")

        agent_context = AgentContext(
           user_command=command or "",
           intent=category,
           screen_available=self.tool_manager.get_tool("Vision") is not None,
           internet_available=self.tool_manager.get_tool("InternetEngine") is not None,
           memory_available=self.tool_manager.get_tool("MemoryEngine") is not None,
           knowledge_available=self.tool_manager.get_tool("KnowledgeEngine") is not None,
           vision_available=self.tool_manager.get_tool("Vision") is not None,
           automation_available=self.tool_manager.get_tool("AutomationEngine") is not None,
        )

        decision = self.agent.decide(agent_context, plan=plan)
        self.last_decision = decision

        if plan is not None:
            self.tool_manager.execute("ContextEngine", "set_goal", command)
            steps = getattr(plan, "steps", [])
            for step in steps:
                description = getattr(step, "description", None) or getattr(step, "action", "")
                if description:
                    self.tool_manager.execute("ContextEngine", "add_pending_task", description)

            return {"route": "execute_plan", "plan": plan}

        if decision.selected_tool == "Vision":
            return "vision"

        if decision.selected_tool in (
            "KnowledgeEngine",
            "InternetEngine",
            "MemoryEngine",
            "PlannerEngine",
            "AutomationEngine",
            "DesktopController",
            "Voice",
            "LLM",
        ):
            return "knowledge"

        if category == "greeting":
            return "greeting"
 
        memory_result = self.tool_manager.execute("MemoryEngine", "is_memory_command", command)
        if memory_result.get("success") and memory_result.get("result"):
            return "knowledge"

        return "unknown"


    def _extract_active_context(self, plan: dict[str, Any]) -> None:
        if not isinstance(plan, dict):
            return

        for step in plan.get("steps", []):
            action = step.get("action", "").lower()
            target = step.get("target")
            if action == "launch application" and isinstance(target, str):
                self.tool_manager.execute("ContextEngine", "set_active_application", target)
            if action == "open website":
                self.tool_manager.execute("ContextEngine", "set_active_application", "browser")
            if "document" in action or "summarize" in action:
                self.tool_manager.execute("ContextEngine", "set_active_document", target or "document")
