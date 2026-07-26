"""Extensible, confidence-scored request routing for EchoBrain."""
from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Callable

from intent import TaskExecutor


@dataclass(frozen=True)
class RoutingDecision:
    """A classifier result, separated from any engine execution."""
    intent: str
    route: str
    engine: str
    confidence: float


Matcher = Callable[[str], float]


class Router:
    """Registry-based router that keeps classification easy to extend."""
    def __init__(self) -> None:
        self.logger = logging.getLogger("echodesk.router")
        # Retain the established runtime integration point.  Classification is
        # handled below, while RuntimeEngine still owns the legacy tool graph.
        self.executor = TaskExecutor()
        self._matchers: list[tuple[str, str, str, Matcher]] = []
        self._register_defaults()
        self.last_decision = RoutingDecision("Conversation", "conversation", "LLM", 0.25)

    def register(self, intent: str, route: str, engine: str, matcher: Matcher) -> None:
        """Register a matcher returning a confidence from 0.0 through 1.0."""
        self._matchers.append((intent, route, engine, matcher))

    def classify(self, command: str | None) -> RoutingDecision:
        text = (command or "").strip().casefold()
        winner: tuple[str, str, str, float] | None = None
        for intent, route, engine, matcher in self._matchers:
            confidence = max(0.0, min(1.0, float(matcher(text))))
            if winner is None or confidence > winner[3]: winner = (intent, route, engine, confidence)
        if winner is None or winner[3] < 0.5:
            decision = RoutingDecision("Conversation", "conversation", "LLM", 0.25)
        else:
            decision = RoutingDecision(*winner)
        self.last_decision = decision
        self.logger.info("[Router] Intent: %s Confidence: %.2f Engine: %s", decision.intent, decision.confidence, decision.engine)
        return decision

    def route(self, command: str | None) -> str:
        """Return the legacy route string while retaining detailed metadata."""
        return self.classify(command).route

    def _register_defaults(self) -> None:
        self.register("DesktopAutomation", "desktop", "DesktopAutomation", self._desktop)
        self.register("Memory", "memory", "MemoryEngine", self._keywords("remember", "save this", "what do you remember", "recall", "my notes"))
        self.register("Vision", "vision", "VisionEngine", self._keywords("what is on my screen", "what's on my screen", "read this text", "analyze this image", "capture screen", "read screen"))
        self.register("Internet", "internet", "InternetEngine", self._keywords("search for", "search the web", "search web", "look up", "latest", "news", "browse the web"))
        self.register("Coding", "coding", "LLMEngine", self._keywords("write python", "write code", "create a class", "generate html", "fix this program", "fix this code"))
        self.register("Knowledge", "knowledge", "KnowledgeEngine", self._keywords("what is", "explain", "define", "how does", "binary tree", "recursion", "quantum computing"))
        self.register("Conversation", "conversation", "LLM", self._keywords("hello", "hi", "how are you", "good morning", "good afternoon", "good evening", "thank you", "thanks", "who are you"))

    @staticmethod
    def _keywords(*phrases: str) -> Matcher:
        def match(text: str) -> float:
            if not text: return 0.0
            return 0.94 if any(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text) for phrase in phrases) else 0.0
        return match

    @staticmethod
    def _desktop(text: str) -> float:
        if not text: return 0.0
        if re.match(r"^(?:open|launch|start|close|minimize|maximize|restore|focus)\b", text): return 0.97
        if "take screenshot" in text or text == "screenshot": return 0.97
        return 0.0
