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
        self.memory = Memory()
        self.memory_controller = memory_controller or self._create_default_memory_controller()

        # Lazy-loaded modules
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

    def process(self, command):

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

            response = (
                "I don't understand that request yet."
            )

        self.memory.remember(command, response)

        return response