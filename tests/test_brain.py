import unittest
from unittest.mock import Mock

from brain.brain import EchoBrain
from context.context import ContextEngine


class TestEchoBrainRouting(unittest.TestCase):

    def test_process_uses_llm_for_general_question_when_knowledge_missing(self):
        knowledge_engine = Mock()
        knowledge_engine.search.return_value = None
        llm_engine = Mock()
        llm_engine.ask.return_value = "An explanation from the LLM."

        context_engine = ContextEngine()
        brain = EchoBrain(
            knowledge_engine=knowledge_engine,
            llm_engine=llm_engine,
            context_engine=context_engine,
        )
        brain.router = Mock(route=Mock(return_value="knowledge"))

        response = brain.process("Explain recursion.")

        self.assertEqual(response, "An explanation from the LLM.")
        llm_engine.ask.assert_called_once()
        self.assertEqual(llm_engine.ask.call_args[0][0], "Explain recursion.")

    def test_process_uses_internet_engine_for_internet_intent(self):
        internet_engine = Mock()
        internet_engine.search.return_value = "Internet search summary."

        brain = EchoBrain(internet_engine=internet_engine)
        brain.router = Mock(route=Mock(return_value="internet"))

        response = brain.process("What happened in AI today?")

        self.assertEqual(response, "Internet search summary.")
        internet_engine.search.assert_called_once_with("What happened in AI today?")

    def test_process_uses_llm_for_greetings(self):
        llm_engine = Mock()
        llm_engine.ask.return_value = "Hello from the LLM."
        context_engine = ContextEngine()

        brain = EchoBrain(llm_engine=llm_engine, context_engine=context_engine)
        brain.router = Mock(route=Mock(return_value="greeting"))

        response = brain.process("hello")

        self.assertEqual(response, "Hello from the LLM.")
        llm_engine.ask.assert_called_once()
        self.assertEqual(llm_engine.ask.call_args[0][0], "hello")

    def test_process_stores_generic_memory_commands(self):
        memory_controller = Mock()
        memory_controller.remember.return_value = {"success": True}

        brain = EchoBrain(memory_controller=memory_controller)
        response = brain.process("remember Buy milk")

        self.assertEqual(response, "I'll remember that Buy milk.")
        memory_controller.remember.assert_called_once_with("Buy milk", "remembered")

    def test_process_uses_vision_engine_for_vision_intent(self):
        brain = EchoBrain()
        brain.router = Mock(route=Mock(return_value="vision"))
        brain.capture = Mock()
        brain.reader = Mock()
        brain.analyzer = Mock()
        brain.capture.take_screenshot.return_value = "screen.png"
        brain.reader.read_image.return_value = "screen text"
        brain.analyzer.analyze.return_value = "Screen analysis result."

        response = brain.process("Read the error on my screen.")

        self.assertEqual(response, "Screen analysis result.")
        brain.capture.take_screenshot.assert_called_once()
        brain.reader.read_image.assert_called_once_with("screen.png")
        brain.analyzer.analyze.assert_called_once_with("screen text")

    def test_process_handles_llm_failure_gracefully(self):
        knowledge_engine = Mock()
        knowledge_engine.search.return_value = None
        llm_engine = Mock()
        llm_engine.ask.side_effect = RuntimeError("LLM unavailable")

        context_engine = ContextEngine()
        brain = EchoBrain(
            knowledge_engine=knowledge_engine,
            llm_engine=llm_engine,
            context_engine=context_engine,
        )
        brain.router = Mock(route=Mock(return_value="knowledge"))

        response = brain.process("Explain recursion.")

        self.assertEqual(
            response,
            "The AI assistant is unavailable right now. Please try again later.",
        )
        llm_engine.ask.assert_called_once()
        self.assertEqual(llm_engine.ask.call_args[0][0], "Explain recursion.")


if __name__ == "__main__":
    unittest.main()
