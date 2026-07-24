import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from runtime.agent_runtime import AgentRuntime


class DummyGoal:
    def __init__(self, goal_id: str):
        self.id = goal_id


class DummyBrain:
    def __init__(self):
        self.goal_manager = Mock()
        self.scheduler = Mock()
        self.run_goal = Mock()


class TestAgentRuntime(unittest.TestCase):
    def test_continue_goal_returns_no_active_goal(self):
        brain = DummyBrain()
        brain.goal_manager.get_next_goal.return_value = None
        runtime = AgentRuntime(brain, tick_interval=0.1)

        result = runtime.continue_goal()

        self.assertFalse(result["success"])
        self.assertIn("No active goal", result["message"])

    def test_tick_executes_next_goal_when_present(self):
        brain = DummyBrain()
        goal = DummyGoal("goal-1")
        brain.goal_manager.get_next_goal.return_value = goal
        brain.run_goal.return_value = SimpleNamespace(status="SUCCESS", final_response="done")
        runtime = AgentRuntime(brain, tick_interval=0.1)
        runtime._running = True

        runtime.tick()

        brain.run_goal.assert_called_once_with(goal.id)
        self.assertEqual(len(runtime.execution_history), 1)
        self.assertEqual(runtime.execution_history[0]["goal_id"], "goal-1")

    def test_start_and_stop_runtime_thread(self):
        brain = DummyBrain()
        goal = DummyGoal("goal-2")
        brain.goal_manager.get_next_goal.return_value = goal
        brain.run_goal.return_value = SimpleNamespace(status="SUCCESS", final_response="done")
        runtime = AgentRuntime(brain, tick_interval=0.1)

        runtime.start()
        time.sleep(0.2)
        runtime.stop()

        self.assertIsNone(runtime._thread)
        self.assertFalse(runtime._paused)

    def test_pause_prevents_tick_execution(self):
        brain = DummyBrain()
        goal = DummyGoal("goal-3")
        brain.goal_manager.get_next_goal.return_value = goal
        brain.run_goal.return_value = SimpleNamespace(status="SUCCESS", final_response="done")
        runtime = AgentRuntime(brain, tick_interval=0.1)

        runtime.pause()
        runtime.tick()

        brain.run_goal.assert_not_called()
        self.assertEqual(len(runtime.execution_history), 0)


if __name__ == "__main__":
    unittest.main()
