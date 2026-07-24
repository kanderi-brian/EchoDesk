import unittest
from types import SimpleNamespace

from planner.planner import ExecutionPlan, Task
from reflection.reflection_engine import ReflectionEngine


class TestReflectionEngine(unittest.TestCase):
    def test_review_execution_returns_feedback_for_success(self):
        reflection = ReflectionEngine()
        plan = ExecutionPlan(goal="test")
        result = SimpleNamespace(status="SUCCESS", final_response="All good")

        feedback = reflection.review_execution("system info", plan, result)

        self.assertTrue(feedback["success"])
        self.assertFalse(feedback["failed_tasks"])
        self.assertFalse(feedback["retry_recommended"])
        self.assertTrue(feedback["confidence"] > 0.5)

    def test_review_execution_suggests_retry_for_failed_tasks(self):
        reflection = ReflectionEngine()
        task = Task(id="1", description="Plugin run", capability="Plugin")
        task.status = "FAILED"
        plan = ExecutionPlan(goal="test", tasks=[task])
        result = SimpleNamespace(status="FAILED", final_response="Plugin failed")

        feedback = reflection.review_execution("system info", plan, result)

        self.assertFalse(feedback["success"])
        self.assertTrue(feedback["retry_recommended"])
        self.assertTrue(feedback["replan_recommended"])
        self.assertIn("Plugin run", feedback["failed_tasks"])

    def test_detect_failures_and_retry_suggestion(self):
        reflection = ReflectionEngine()
        feedback = {"success": False, "retry_recommended": True, "replan_recommended": True}

        self.assertTrue(reflection.detect_failures(feedback))
        self.assertTrue(reflection.suggest_retry(feedback))
        self.assertTrue(reflection.suggest_replan(feedback))


if __name__ == "__main__":
    unittest.main()
