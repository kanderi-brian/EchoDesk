import re
from typing import Any, Dict, Optional

from planner.planner import PlannerEngine
from tools.manager import ToolManager

from llm.engine import LLMEngine
from memory_engine.memory_engine import MemoryEngine


class KnowledgeEngine:

    DEFAULT_FACTS: Dict[str, str] = {
        "who invented python": "Python was created by Guido van Rossum and first released in 1991.",
        "what is python": "Python is a high-level programming language known for its simplicity and versatility.",
        "what is ai": "Artificial Intelligence is the simulation of human intelligence by computers.",
        "what is echodesk": "EchoDesk is an AI desktop assistant that can see the screen, understand it, remember conversations and automate tasks.",
        "who are you": "I am EchoDesk, your personal desktop AI assistant.",
        "what is machine learning": "Machine learning is a field of artificial intelligence focused on teaching computers to learn from data without being explicitly programmed.",
        "what is object-oriented programming": "Object-oriented programming is a programming paradigm based on objects, classes, inheritance, encapsulation, and polymorphism.",
        "what is a function": "A function is a reusable block of organized, modular code that performs a single action or calculation.",
    }

    UNKNOWN_RESPONSE = (
        "I don't have a direct factual lookup for that question, but I can provide an answer from the language model."
    )

    def __init__(self, llm_engine: Optional[LLMEngine] = None):
        self.memory_engine = MemoryEngine()
        self.planner_engine = PlannerEngine()
        self.llm_engine = llm_engine
        self.facts = self.DEFAULT_FACTS.copy()

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

    def search(self, question: str) -> str:
        normalized_question = self._normalize(question)
        if not normalized_question:
            return "I could not understand that question."

        memory_answer = self.memory_engine.process_command(question)
        if memory_answer is not None:
            return memory_answer

        context_answer = self._search_context(normalized_question)
        if context_answer is not None:
            return context_answer

        local_answer = self._lookup_local_fact(normalized_question)
        if local_answer is not None:
            return local_answer

        if self.llm_engine is not None:
            return self._fallback_to_llm(question, normalized_question)

        return "I don't have enough knowledge available right now."

    def _lookup_local_fact(self, question: str) -> Optional[str]:
        exact = self.facts.get(question)
        if exact:
            return exact

        for key, answer in self.facts.items():
            if key in question or question in key:
                return answer

        return None

    def _fallback_to_llm(self, question: str, normalized_question: str) -> str:
        if self.llm_engine is None:
            return "I don't have enough knowledge available right now."

        context = self._build_context(normalized_question)
        try:
            response = self.llm_engine.ask(question, context=context)
        except Exception:
            return self.UNKNOWN_RESPONSE
        if isinstance(response, str) and response.strip() and not response.lower().startswith("llm provider failed:"):
            return response.strip()
        return self.UNKNOWN_RESPONSE

    def _build_context(self, question: str) -> str | None:
        lines = []
        local_answer = self._lookup_local_fact(question)
        if local_answer:
            lines.append(f"Known fact: {local_answer}")

        memory_answer = self.memory_engine.process_command(question)
        if memory_answer is not None and memory_answer != local_answer:
            lines.append(f"Memory clue: {memory_answer}")

        if not lines:
            return None

        return "\n".join(lines)

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

    def _normalize(self, text: str) -> str:
        if not isinstance(text, str):
            return ""
        normalized = text.strip().lower()
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized
