import os
import tempfile
import unittest

from history.history_engine import HistoryEngine


class TestHistoryEngine(unittest.TestCase):
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.history_path = self.temp_file.name
        self.temp_file.close()
        os.unlink(self.history_path)
        self.engine = HistoryEngine(history_file=self.history_path)

    def tearDown(self):
        if os.path.exists(self.history_path):
            os.remove(self.history_path)

    def test_record_goal_and_reflection_events(self):
        self.engine.record_goal_event(type("Goal", (), {"id": "1", "title": "Test", "status": "Pending"})(), "execution_started", "Started")
        self.engine.record_reflection({"command": "test", "success": True})

        history = self.engine.get_history()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["event_type"], "goal_execution_started")
        self.assertEqual(history[1]["event_type"], "reflection")

    def test_record_plan_persists_task_summary(self):
        plan = type("Plan", (), {"tasks": []})()
        self.engine.record_plan(plan, "SUCCESS", type("Result", (), {"final_response": "OK"})())

        history = self.engine.get_history("plan_completed")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["payload"]["status"], "SUCCESS")

    def test_get_goal_history_filters_by_goal_id(self):
        self.engine.record_goal_event(type("Goal", (), {"id": "goal-123", "title": "Test", "status": "Pending"})(), "execution_started", "Started")
        self.engine.record_goal_event(type("Goal", (), {"id": "goal-456", "title": "Other", "status": "Pending"})(), "execution_started", "Started")

        goal_history = self.engine.get_goal_history("goal-123")
        self.assertEqual(len(goal_history), 1)
        self.assertEqual(goal_history[0]["payload"]["goal_id"], "goal-123")


if __name__ == "__main__":
    unittest.main()
