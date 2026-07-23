import datetime
import logging
import re
import time
from typing import Any, Optional

from brain.router import Router
from context.context import get_context_engine
from memory.controller import MemoryController
from memory.memory import Memory
from vision.capture import ScreenCapture
from vision.reader import ScreenReader
from vision.analyzer import ScreenAnalyzer
from knowledge.knowledge import KnowledgeEngine


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

        # Lazy-loaded vision modules
        self.capture = None
        self.reader = None
        self.analyzer = None

        self.logger = logging.getLogger("echodesk.brain")

    def load_vision(self):

        if self.capture is None:

            print("Loading Vision Engine...")

            self.capture = ScreenCapture()
            self.reader = ScreenReader()
            self.analyzer = ScreenAnalyzer()

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

    def process(self, command):

        start_time = time.perf_counter()
        selected_engines = []
        route = None

        if self.context_engine is not None:
            try:
                self.context_engine.expire_context()
                self.context_engine.add_user_message(command)
            except Exception:
                pass

        # Check if this is a long-term memory command
        memory_response = self._handle_memory_command(command)

        if memory_response:
            selected_engines.append("MemoryEngine")
            self.memory.remember(command, memory_response)
            self.logger.info(
                "Processed memory command. route=memory selected_engines=%s elapsed=%.3fs",
                selected_engines,
                time.perf_counter() - start_time,
            )
            return memory_response

        intent = self.router.route(command)
        route = intent

        try:
            if intent == "greeting":
                selected_engines.append("LLMEngine")
                response = self._llm_fallback(command)

            elif intent == "time":
                selected_engines.append("Brain")
                now = datetime.datetime.now()
                response = f"The current time is {now.strftime('%H:%M:%S')}"

            elif intent == "history":
                selected_engines.append("MemoryEngine")
                history = self.memory.recall()
                response = f"I remember {len(history)} conversations."

            elif intent == "screenshot":
                selected_engines.append("Vision")
                self.load_vision()
                image = self.capture.take_screenshot()
                response = f"Screenshot saved to {image}"

            elif intent == "vision":
                selected_engines.append("Vision")
                self.load_vision()
                image = self.capture.take_screenshot()
                text = self.reader.read_image(image)
                response = self.analyzer.analyze(text)

            elif intent == "internet":
                selected_engines.append("InternetEngine")
                if self.internet_engine is not None:
                    response = self.internet_engine.search(command)
                else:
                    response = self._llm_fallback(command)

            elif intent == "knowledge":
                selected_engines.append("KnowledgeEngine")
                response = self.knowledge.search(command)
                if not response:
                    selected_engines.append("LLMEngine")
                    response = self._llm_fallback(command)

            else:
                selected_engines.append("LLMEngine")
                response = self._llm_fallback(command)

        except Exception as error:
           self.logger.error(
               "Failed to process command. route=%s selected_engines=%s error=%s",
               route,
               selected_engines,
               error,
               exc_info=True,
           )
           response = "Something went wrong while processing your request. Please try again."

        if self.context_engine is not None:
           try:
               self.context_engine.add_assistant_message(response)
               self._update_context_from_command(command, response)
           except Exception:
               pass

        self.memory.remember(command, response)
        self.logger.info(
            "Processed command. route=%s selected_engines=%s elapsed=%.3fs",
            route,
            selected_engines,
            time.perf_counter() - start_time,
        )
        return response

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
