from typing import Any

from planner.planner import PlannerEngine
from tools.manager import ToolManager

from memory_engine.memory_engine import MemoryEngine


class KnowledgeEngine:

    def __init__(self):

        self.facts = {

            "who invented python":
                "Python was created by Guido van Rossum and first released in 1991.",

            "what is python":
                "Python is a high-level programming language known for its simplicity and versatility.",

            "what is ai":
                "Artificial Intelligence is the simulation of human intelligence by computers.",

            "what is echodesk":
                "EchoDesk is an AI desktop assistant that can see the screen, understand it, remember conversations and automate tasks.",

            "who are you":
                "I am EchoDesk, your personal desktop AI assistant."
        }

        self.memory_engine = MemoryEngine()
        self.planner_engine = PlannerEngine()

    def _agent_engine(self):
        try:
            tool_manager = ToolManager()
            registration_result = tool_manager.register_default_tools()
            if not registration_result.get("success"):
                return None
            return tool_manager.get_tool("AgentEngine")
        except Exception:
            return None

    def _format_agent_response(self, response: dict[str, Any]) -> str:
        if not isinstance(response, dict):
            return str(response)

        message = response.get("message", "Agent execution completed.")
        result = response.get("result")
        if isinstance(result, dict):
            summary = result.get("result")
            if isinstance(summary, dict):
                plan_summary = summary.get("goal")
                status = summary.get("status")
                return f"{message} Goal: {plan_summary}. Status: {status}."
            if summary is not None:
                return f"{message} {summary}"
        return message

    def search(self, question):

        question = question.lower().strip()

        if not question:
            return None

        memory_answer = self.memory_engine.process_command(question)
        if memory_answer is not None:
            return memory_answer

        context_answer = self._search_context(question)
        if context_answer is not None:
            return context_answer

        local_answer = self.facts.get(question)
        if local_answer is not None:
            return local_answer

        return None

    def _search_context(self, question: str) -> str | None:
        normalized = question.strip().lower()
        if not normalized:
            return None

        try:
            from context.context import get_context_engine

            context_engine = get_context_engine()
        except Exception:
            return None

        if normalized == "continue":
            pending = context_engine.get_pending_tasks().get("result", [])
            if pending:
                return f"You have pending tasks: {', '.join(pending)}."
            return "There are no pending tasks to continue."

        if "last request" in normalized or "last command" in normalized:
            history = context_engine.get_recent_history().get("result", [])
            user_messages = [entry.get("message") for entry in history if entry.get("role") == "user"]
            if not user_messages:
                return "I do not have a record of your last request."
            if len(user_messages) > 1 and user_messages[-1] == question:
                return f"Your last request was: {user_messages[-2]}"
            return f"Your last request was: {user_messages[-1]}"

        if "current goal" in normalized or ("goal" in normalized and "last" not in normalized):
            goal = context_engine.get_goal().get("result")
            if goal:
                return f"Your current goal is: {goal}"
            return "No current goal has been set yet."

        if "pending task" in normalized or "pending tasks" in normalized:
            pending = context_engine.get_pending_tasks().get("result", [])
            if pending:
                return f"Pending tasks: {', '.join(pending)}"
            return "No pending tasks are currently tracked."

        return None
