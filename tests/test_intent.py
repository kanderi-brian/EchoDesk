import re
import unittest

from intent.intent import TaskExecutor


class TestIntentRouting(unittest.TestCase):

    def test_task_executor_does_not_route_non_time_question_to_time(self):
        executor = TaskExecutor()
        route = executor.execute("What is time complexity?")

        self.assertNotEqual(route, "time")

    def test_task_executor_routes_execution_control_commands(self):
        executor = TaskExecutor()
        self.assertEqual(executor.execute("continue"), "resume_execution")
        self.assertEqual(executor.execute("resume"), "resume_execution")
        self.assertEqual(executor.execute("cancel"), "cancel_execution")
        self.assertEqual(executor.execute("retry the failed step"), "retry_step")
        self.assertEqual(executor.execute("skip this step"), "skip_step")


if __name__ == "__main__":
    unittest.main()
