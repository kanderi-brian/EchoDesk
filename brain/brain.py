import datetime
import re
from typing import Optional

from brain.router import Router
from memory.controller import MemoryController
from memory.memory import Memory
from vision.capture import ScreenCapture
from vision.reader import ScreenReader
from vision.analyzer import ScreenAnalyzer
from knowledge.knowledge import KnowledgeEngine


class EchoBrain:

    def __init__(self, memory_controller: Optional[MemoryController] = None):

        self.router = Router()

        # Conversation history
        self.memory = Memory()

        # Long-term memory (dependency injection)
        self.memory_controller = memory_controller

        # Lazy-loaded vision modules
        self.capture = None
        self.reader = None
        self.analyzer = None

        self.knowledge = KnowledgeEngine()

    def load_vision(self):

        if self.capture is None:

            print("Loading Vision Engine...")

            self.capture = ScreenCapture()
            self.reader = ScreenReader()
            self.analyzer = ScreenAnalyzer()

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

        # Recall command
        recall = re.match(
            r"(?:what\s+is|where\s+is)\s+(.+)",
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

        # Check if this is a long-term memory command
        memory_response = self._handle_memory_command(command)

        if memory_response:

            self.memory.remember(command, memory_response)

            return memory_response

        intent = self.router.route(command)

        if intent == "greeting":

            response = "Hello! I am EchoDesk. How can I help you?"

        elif intent == "time":

            now = datetime.datetime.now()

            response = f"The current time is {now.strftime('%H:%M:%S')}"

        elif intent == "history":

            history = self.memory.recall()

            response = f"I remember {len(history)} conversations."

        elif intent == "screenshot":

            self.load_vision()

            image = self.capture.take_screenshot()

            response = f"Screenshot saved to {image}"

        elif intent == "vision":

            self.load_vision()

            image = self.capture.take_screenshot()

            text = self.reader.read_image(image)

            response = self.analyzer.analyze(text)

        elif intent == "knowledge":

            answer = self.knowledge.search(command)

            if answer:

                response = answer

            else:

                response = (
                    "I don't know that yet. "
                    "Soon I'll be able to search AI or the web."
                )

        else:

            response = "I don't understand that request yet."

        self.memory.remember(command, response)

        return response