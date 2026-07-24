import unittest
from unittest.mock import Mock

from brain.brain import EchoBrain
from context.context import ContextEngine


class TestEchoBrainGoals(unittest.TestCase):
    def test_create_and_list_goals(self):
        brain = EchoBrain(llm_engine=Mock())

        response = brain.process("create goal Finish project")
        self.assertIn("Created goal", response)

        active = brain.process("show active goals")
        self.assertIn("Finish project", active)

    def test_continue_my_work_runs_goal(self):
        llm_engine = Mock()
        llm_engine.ask.return_value = "Task completed"
        brain = EchoBrain(llm_engine=llm_engine, context_engine=ContextEngine())

        brain.process("create goal Learn the new feature")
        response = brain.process("continue my work")

        self.assertEqual(response, "[LLM] Task completed")
        goal_list = brain.list_goals()
        self.assertTrue(any(goal["title"] == "Learn the new feature" for goal in goal_list))

    def test_retry_failed_goal_changes_status(self):
        llm_engine = Mock()
        llm_engine.ask.return_value = "Task completed"
        brain = EchoBrain(llm_engine=llm_engine, context_engine=ContextEngine())

        brain.process("create goal Finish task")
        goal = brain.goal_manager.get_next_goal()
        goal.status = "Failed"
        brain.goal_manager.save()

        response = brain.process("retry failed goal")
        self.assertEqual(response, "[LLM] Task completed")
        self.assertEqual(brain.goal_manager.get_goal(goal.id).status, "Completed")


if __name__ == "__main__":
    unittest.main()
