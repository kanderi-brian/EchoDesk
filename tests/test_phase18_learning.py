"""Phase 18 learning and personalization regression coverage."""
import tempfile
import unittest
from pathlib import Path

from learning import LearningEngine
from memory_engine.memory_engine import MemoryEngine


class TestLearningEngine(unittest.TestCase):
    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "memory.json"
        self.engine = LearningEngine(MemoryEngine(str(self.path)))

    def test_records_and_ranks_successful_strategy(self):
        self.engine.record_outcome("python test workflow", True, confidence=.9, verification_success=True, duration=.1)
        self.engine.record_outcome("slow workflow", False, confidence=.1, verification_success=False, duration=5)
        self.assertEqual(self.engine.recommend_strategy("python test")[0].name, "python test workflow")

    def test_recovery_recommends_failed_patterns(self):
        self.engine.record_outcome("recover import error", False, failure="ImportError", confidence=.2)
        self.assertEqual(self.engine.recommend_recovery("ImportError")[0].name, "recover import error")

    def test_workflow_reuse(self):
        self.engine.record_outcome("create python project", True, workflow="python project", confidence=.8)
        self.assertTrue(self.engine.recommend_workflow("python project"))

    def test_explanation_contains_verification_rate(self):
        self.engine.record_outcome("strategy", True, confidence=.9, verification_success=True)
        self.assertIn("verification rate", self.engine.explain_strategy("strategy"))

    def test_preferences_persist(self):
        self.engine.update_preference("Coding", "Language", "Python", .8)
        reloaded = LearningEngine(MemoryEngine(str(self.path)))
        self.assertEqual(reloaded.get_statistics()["preferences"][0].value, "Python")

    def test_preference_decay(self):
        self.engine.update_preference("Coding", "Language", "Python", .8)
        self.engine.decay_preferences(.2)
        self.assertLessEqual(self.engine.get_statistics()["preferences"][0].confidence, .6)

    def test_plan_recommendation_is_safe_metadata(self):
        self.engine.record_outcome("safe approach", True, confidence=.7)
        plan = self.engine.recommend_plan("safe approach")
        self.assertIn("strategies", plan)
        self.assertNotIn("code", plan)


def _make_outcome_case(index):
    def test(self):
        strategy = f"workflow {index}"
        record = self.engine.record_outcome(strategy, index % 2 == 0, workflow="shared" if index % 3 == 0 else "", confidence=index / 50, verification_success=index % 2 == 0, duration=index / 100)
        self.assertEqual(record.name, strategy)
        self.assertEqual(record.usage_frequency, 1)
    return test


for _index in range(1, 44):
    setattr(TestLearningEngine, f"test_learning_event_{_index:02d}", _make_outcome_case(_index))
