import unittest
from unittest.mock import Mock

from knowledge.knowledge import KnowledgeEngine


class TestKnowledgeEngine(unittest.TestCase):
    def test_known_answer_returns_local_fact(self):
        engine = KnowledgeEngine()
        answer = engine.search("who invented python")

        self.assertIsInstance(answer, str)
        self.assertIn("Guido van Rossum", answer)

    def test_unknown_answer_uses_llm_fallback(self):
        llm = Mock()
        llm.ask.return_value = "Lisps are a family of programming languages."
        engine = KnowledgeEngine(llm_engine=llm)
        answer = engine.search("what is the capital of lisp")

        self.assertEqual(answer, "Lisps are a family of programming languages.")
        llm.ask.assert_called_once()

    def test_unknown_answer_without_llm_returns_clear_fallback(self):
        engine = KnowledgeEngine()

        self.assertEqual(
            engine.search("what is the capital of lisp"),
            "I don't have enough knowledge available right now.",
        )


if __name__ == "__main__":
    unittest.main()
