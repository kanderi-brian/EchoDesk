import os
import tempfile
import unittest
from pathlib import Path

from memory_engine.memory_engine import MemoryEngine, UserPreference


class TestLearningEngine(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.file_path = Path(self.temp_dir.name) / "memory.json"
        self.engine = MemoryEngine(file_path=str(self.file_path))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_remember_preference_creates_new_preference(self):
        preference = self.engine.remember_preference(
            category="Editor",
            key="Preferred Editor",
            value="VS Code",
            confidence=0.6,
            learned_from="explicit",
        )

        self.assertIsInstance(preference, UserPreference)
        self.assertEqual(preference.category, "Editor")
        self.assertEqual(preference.key, "Preferred Editor")
        self.assertEqual(preference.value, "VS Code")
        self.assertEqual(preference.confidence, 0.6)
        self.assertEqual(preference.learned_from, "explicit")
        self.assertEqual(preference.usage_count, 1)

    def test_update_preference_increases_usage_and_confidence(self):
        self.engine.remember_preference("Browser", "Preferred Browser", "Chrome", confidence=0.5)
        updated = self.engine.update_preference("Browser", "Preferred Browser", "Chrome", confidence=0.7)

        self.assertIsNotNone(updated)
        self.assertEqual(updated.value, "Chrome")
        self.assertEqual(updated.confidence, 0.7)
        self.assertEqual(updated.usage_count, 2)

    def test_remove_preference_returns_true_when_removed(self):
        self.engine.remember_preference("Theme", "Theme", "Dark")
        removed = self.engine.remove_preference("Theme", "Theme")

        self.assertTrue(removed)
        self.assertIsNone(self.engine.get_preference("Theme", "Theme"))

    def test_learn_increases_confidence_for_repeated_behavior(self):
        self.engine.learn("use chrome to browse", capability="Internet", success=True, response="ok", duration=0.1, engine="Internet")
        self.engine.learn("use chrome again", capability="Internet", success=True, response="ok", duration=0.2, engine="Internet")

        pref = self.engine.get_preference("Browser", "Preferred Browser")
        self.assertIsNotNone(pref)
        self.assertEqual(pref.value, "Chrome")
        self.assertGreaterEqual(pref.confidence, 0.5)
        self.assertGreaterEqual(pref.usage_count, 2)

    def test_statistics_include_command_history_and_average_length(self):
        self.engine.learn("hello world", capability="LLM", success=True, response="hi", duration=0.05, engine="LLM")
        self.engine.learn("open chrome", capability="Internet", success=True, response="ok", duration=0.1, engine="Internet")

        stats = self.engine.get_statistics()
        self.assertEqual(stats["total_commands"], 2)
        self.assertEqual(stats["session_count"], 2)
        self.assertEqual(stats["successful_executions"], 2)
        self.assertEqual(stats["failed_executions"], 0)
        self.assertEqual(stats["command_history_size"], 2)
        self.assertGreater(stats["average_command_length"], 0)

    def test_command_history_limits_to_latest_100(self):
        for i in range(105):
            self.engine.learn(f"cmd {i}", capability="LLM", success=True, response="ok", duration=0.01, engine="LLM")

        self.assertEqual(len(self.engine._payload.get("command_history", [])), 100)
        self.assertEqual(self.engine._payload["command_history"][0]["command"], "cmd 5")

    def test_recommend_returns_personalized_messages(self):
        self.engine.remember_preference("Language", "Programming Language", "Python", confidence=0.7)
        self.engine.remember_preference("Browser", "Preferred Browser", "Chrome", confidence=0.6)
        self.engine.learn("what is a python list", capability="Knowledge", success=True, response="answer", duration=0.1, engine="Knowledge")

        recs = self.engine.recommend()
        self.assertTrue(any("Python" in text for text in recs))
        self.assertTrue(any("Chrome" in text for text in recs))


if __name__ == "__main__":
    unittest.main()
