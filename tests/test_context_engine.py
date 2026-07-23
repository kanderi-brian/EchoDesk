import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock

from context.context import ContextEngine
from brain.brain import EchoBrain


class TestContextEngine(unittest.TestCase):

    def test_adds_and_retrieves_recent_messages(self):
        context_engine = ContextEngine(max_turns=10)

        result = context_engine.add_user_message("Hello")
        self.assertTrue(result["success"])

        result = context_engine.add_assistant_message("Hi there")
        self.assertTrue(result["success"])

        history = context_engine.get_recent_history()["result"]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[1]["role"], "assistant")
        self.assertEqual(history[1]["message"], "Hi there")

    def test_context_expiration_clears_temporary_state(self):
        context_engine = ContextEngine()
        context_engine.add_user_message("Hello")
        context_engine.set_active_application("Notepad")

        context_engine._last_updated = datetime.now() - timedelta(seconds=3601)
        result = context_engine.expire_context(max_age_seconds=3600)

        self.assertTrue(result["success"])
        self.assertIsNone(context_engine.get_active_application().get("result"))
        self.assertEqual(context_engine.get_recent_history().get("result"), [])

    def test_active_project_and_recent_files_are_stored(self):
        context_engine = ContextEngine()

        context_engine.set_active_project("My Project")
        context_engine.add_recent_file("/path/to/file.py")
        context_engine.add_recent_file("/path/to/file.py")

        self.assertEqual(context_engine.get_active_project()["result"], "My Project")
        self.assertEqual(context_engine.get_recent_files()["result"], ["/path/to/file.py"])


class TestEchoBrainContextIntegration(unittest.TestCase):

    def test_process_records_user_and_assistant_messages(self):
        llm_engine = Mock()
        llm_engine.ask.return_value = "Hello from the LLM."
        context_engine = ContextEngine()

        brain = EchoBrain(llm_engine=llm_engine, context_engine=context_engine)
        brain.router = Mock(route=Mock(return_value="greeting"))

        response = brain.process("hello")

        self.assertEqual(response, "Hello from the LLM.")
        history = context_engine.get_recent_history()["result"]
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[0]["message"], "hello")
        self.assertEqual(history[1]["role"], "assistant")
        self.assertEqual(history[1]["message"], "Hello from the LLM.")

    def test_llm_fallback_includes_relevant_memory_context(self):
        llm_engine = Mock()
        llm_engine.ask.return_value = "Answer from LLM."
        memory_controller = Mock()
        memory_controller.search.return_value = {
            "success": True,
            "result": [Mock(key="favorite editor", value="VS Code")],
        }
        context_engine = ContextEngine()

        brain = EchoBrain(
            llm_engine=llm_engine,
            memory_controller=memory_controller,
            context_engine=context_engine,
        )
        brain.router = Mock(route=Mock(return_value="greeting"))

        response = brain.process("hello")

        self.assertEqual(response, "Answer from LLM.")
        llm_engine.ask.assert_called_once()
        called_args = llm_engine.ask.call_args
        self.assertEqual(called_args[0][0], "hello")
        self.assertIn("Relevant memories", called_args[1]["context"])
        self.assertIn("favorite editor: VS Code", called_args[1]["context"])
