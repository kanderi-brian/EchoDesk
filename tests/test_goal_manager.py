import os
import tempfile
import unittest
from datetime import datetime, timedelta

from goal_manager.goal_manager import GoalManager, GoalStatus


class TestGoalManager(unittest.TestCase):
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.goal_path = self.temp_file.name
        self.temp_file.close()
        os.unlink(self.goal_path)
        self.manager = GoalManager(storage_path=self.goal_path)

    def tearDown(self):
        if os.path.exists(self.goal_path):
            os.remove(self.goal_path)

    def test_create_and_persist_goal(self):
        goal = self.manager.create_goal("Write report", description="Write a report for the team.")
        self.assertIsNotNone(goal.id)
        self.assertEqual(goal.title, "Write report")
        self.assertEqual(goal.description, "Write a report for the team.")

        loaded = GoalManager(storage_path=self.goal_path)
        self.assertEqual(len(loaded.get_all_goals()), 1)
        self.assertEqual(loaded.get_goal(goal.id).title, "Write report")

    def test_resume_interrupted_goals(self):
        goal = self.manager.create_goal("Sync files", description="Sync project files.")
        goal.status = GoalStatus.Running
        self.manager.save()

        manager = GoalManager(storage_path=self.goal_path)
        resumed = manager.resume_interrupted_goals()
        self.assertEqual(resumed, 1)
        self.assertEqual(manager.get_goal(goal.id).status, GoalStatus.Pending)

    def test_get_next_goal_respects_dependencies(self):
        first = self.manager.create_goal("Prepare data", description="Prepare dataset.")
        second = self.manager.create_goal("Train model", description="Train the machine learning model.", dependencies=[first.id])

        next_goal = self.manager.get_next_goal()
        self.assertEqual(next_goal.id, first.id)

        self.manager.complete_goal(first.id)
        next_goal = self.manager.get_next_goal()
        self.assertEqual(next_goal.id, second.id)

    def test_get_unfinished_goals_includes_failed_and_paused(self):
        goal = self.manager.create_goal("Review results", description="Review the analysis.")
        self.assertIn(goal, self.manager.get_unfinished_goals())
        self.manager.pause_goal(goal.id)
        self.assertIn(goal, self.manager.get_unfinished_goals())
        self.manager.cancel_goal(goal.id)
        self.assertNotIn(goal, self.manager.get_unfinished_goals())


if __name__ == "__main__":
    unittest.main()
