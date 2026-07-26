import unittest
from unittest.mock import Mock

from brain.brain import EchoBrain
from brain.router import Router


class IntentRouterTests(unittest.TestCase):
    def setUp(self): self.router = Router()

    def test_routes_required_categories_with_confidence(self):
        cases = {
            "hello": ("Conversation", "conversation", "LLM"),
            "open calculator": ("DesktopAutomation", "desktop", "DesktopAutomation"),
            "latest AI news": ("Internet", "internet", "InternetEngine"),
            "what is recursion": ("Knowledge", "knowledge", "KnowledgeEngine"),
            "remember this": ("Memory", "memory", "MemoryEngine"),
            "what is on my screen": ("Vision", "vision", "VisionEngine"),
            "write Python code": ("Coding", "coding", "LLMEngine"),
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                decision = self.router.classify(command)
                self.assertEqual(expected, (decision.intent, decision.route, decision.engine))
                self.assertGreaterEqual(decision.confidence, 0.9)

    def test_low_confidence_uses_conversation_llm_fallback(self):
        decision = self.router.classify("please help with something unusual")
        self.assertEqual(("Conversation", "LLM"), (decision.intent, decision.engine))
        self.assertLess(decision.confidence, 0.5)

    def test_route_remains_legacy_string_api(self):
        self.assertEqual("internet", self.router.route("search for Python tutorials"))

    def test_router_writes_structured_log(self):
        with self.assertLogs("echodesk.router", "INFO") as logs: self.router.classify("open chrome")
        self.assertIn("Intent: DesktopAutomation", logs.output[0])
        self.assertIn("Engine: DesktopAutomation", logs.output[0])

    def test_desktop_requests_bypass_llm_and_use_existing_controller(self):
        controller = Mock(); controller.open_application.return_value = {"message": "Chrome opened"}
        llm = Mock(); brain = EchoBrain(desktop_controller=controller, llm_engine=llm)
        self.assertEqual("Chrome opened", brain.process("open chrome"))
        controller.open_application.assert_called_once_with("chrome"); llm.ask.assert_not_called()

    def test_knowledge_miss_falls_back_to_llm(self):
        knowledge = Mock(); knowledge.search.return_value = None
        llm = Mock(); llm.ask.return_value = "LLM explanation"
        brain = EchoBrain(knowledge_engine=knowledge, llm_engine=llm)
        self.assertEqual("LLM explanation", brain.process("explain binary trees"))
        knowledge.search.assert_called_once_with("explain binary trees"); llm.ask.assert_called_once()


if __name__ == "__main__": unittest.main()
