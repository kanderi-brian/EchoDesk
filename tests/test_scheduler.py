import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta

from goal_manager.goal_manager import GoalManager
from scheduler.scheduler import Scheduler


class TestScheduler(unittest.TestCase):
    def setUp(self):
        self.goal_file = tempfile.NamedTemporaryFile(delete=False)
        self.goal_path = self.goal_file.name
        self.goal_file.close()
        os.unlink(self.goal_path)

        self.schedule_file = tempfile.NamedTemporaryFile(delete=False)
        self.schedule_path = self.schedule_file.name
        self.schedule_file.close()
        os.unlink(self.schedule_path)

        self.goal_manager = GoalManager(storage_path=self.goal_path)
        self.scheduler = Scheduler(schedule_file=self.schedule_path)

    def tearDown(self):
        if os.path.exists(self.goal_path):
            os.remove(self.goal_path)
        if os.path.exists(self.schedule_path):
            os.remove(self.schedule_path)

    def test_activate_due_goal_marks_goal_pending(self):
        goal = self.goal_manager.create_goal("Daily review", description="Review daily updates.")
        due_time = datetime.now(UTC) - timedelta(minutes=1)
        entry = self.scheduler.schedule_goal(goal.id, due_time, recurrence="once")

        activated = self.scheduler.activate_due_goals(self.goal_manager)

        self.assertEqual(len(activated), 1)
        self.assertEqual(activated[0].id, entry.id)
        self.assertEqual(self.goal_manager.get_goal(goal.id).status, "Pending")
        self.assertFalse(self.scheduler.entries[entry.id].enabled)

    def test_activate_daily_schedule_updates_next_run(self):
        goal = self.goal_manager.create_goal("Backup data", description="Backup files daily.")
        due_time = datetime.now(UTC) - timedelta(minutes=1)
        entry = self.scheduler.schedule_goal(goal.id, due_time, recurrence="daily")
        original_run_at = entry.run_at

        activated = self.scheduler.activate_due_goals(self.goal_manager)

        self.assertEqual(len(activated), 1)
        self.assertTrue(self.scheduler.entries[entry.id].enabled)
        self.assertNotEqual(self.scheduler.entries[entry.id].run_at, original_run_at)
        self.assertTrue(self.scheduler.entries[entry.id].run_at.endswith("Z"))

    def test_cancel_schedule_removes_entry(self):
        goal = self.goal_manager.create_goal("Archive logs", description="Archive old logs.")
        due_time = datetime.now(UTC) + timedelta(minutes=10)
        entry = self.scheduler.schedule_goal(goal.id, due_time, recurrence="once")

        cancelled = self.scheduler.cancel_schedule(entry.id)

        self.assertTrue(cancelled)
        self.assertNotIn(entry.id, self.scheduler.entries)


if __name__ == "__main__":
    unittest.main()
