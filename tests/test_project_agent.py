import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from agent.models import ExecutionState
from agent.project_agent import ProjectAgent
from brain.brain import EchoBrain
from planner.planner import ExecutionPlan, Task


class FakePlanner:
    def __init__(self, tasks=None):
        self.tasks = tasks or [Task(id="one", description="Complete task", capability="LLM")]

    def plan(self, objective):
        return ExecutionPlan(goal=objective, tasks=list(self.tasks), required_capabilities=[task.capability for task in self.tasks])


class FakeExecutor:
    def __init__(self, status="SUCCESS", output="completed"):
        self.status, self.output, self.calls = status, output, 0

    def execute_plan(self, plan, command):
        self.calls += 1
        return SimpleNamespace(status=self.status, final_response=self.output)


class TestProjectAgent(unittest.TestCase):
    def make_agent(self, **kwargs):
        return ProjectAgent(planner=kwargs.get("planner", FakePlanner()), executor=kwargs.get("executor", FakeExecutor()), retry_limit=kwargs.get("retry_limit", 1), approval_callback=kwargs.get("approval_callback"))

    def test_classifies_coding_goal(self):
        self.assertEqual(self.make_agent().classify_goal("implement Python tests"), "coding")

    def test_classifies_desktop_goal(self):
        self.assertEqual(self.make_agent().classify_goal("organize a desktop folder"), "desktop automation")

    def test_classifies_research_goal(self):
        self.assertEqual(self.make_agent().classify_goal("research current news"), "research")

    def test_classifies_mixed_goal(self):
        self.assertEqual(self.make_agent().classify_goal("research and implement code"), "mixed")

    def test_add_goal_queues_goal(self):
        agent = self.make_agent()
        goal = agent.add_goal("do work")
        self.assertEqual(agent.goals[goal.id].status, ExecutionState.QUEUED)

    def test_add_goal_rejects_empty_objective(self):
        with self.assertRaises(ValueError):
            self.make_agent().add_goal(" ")

    def test_run_next_completes_goal(self):
        agent = self.make_agent()
        goal = agent.add_goal("do work")
        self.assertEqual(agent.run_next().status, ExecutionState.COMPLETED)
        self.assertEqual(goal.completed_tasks, ["one"])

    def test_goal_progress_reports_completed_and_remaining_tasks(self):
        agent = self.make_agent(planner=FakePlanner([Task(id="one", description="one", capability="LLM"), Task(id="two", description="two", capability="LLM")]))
        goal = agent.add_goal("do work")
        agent.run_goal(goal.id)
        report = agent.get_progress(goal.id)
        self.assertEqual((report.completed_tasks, report.remaining_tasks), (2, 0))

    def test_pause_goal(self):
        agent = self.make_agent()
        goal = agent.add_goal("do work")
        self.assertTrue(agent.pause_goal(goal.id))
        self.assertEqual(goal.status, ExecutionState.PAUSED)

    def test_resume_goal_requeues_goal(self):
        agent = self.make_agent()
        goal = agent.add_goal("do work")
        agent.pause_goal(goal.id)
        self.assertTrue(agent.resume_goal(goal.id))
        self.assertEqual(goal.status, ExecutionState.QUEUED)

    def test_cancel_goal(self):
        agent = self.make_agent()
        goal = agent.add_goal("do work")
        self.assertTrue(agent.cancel_goal(goal.id))
        self.assertEqual(goal.status, ExecutionState.CANCELLED)

    def test_remove_goal(self):
        agent = self.make_agent()
        goal = agent.add_goal("do work")
        self.assertTrue(agent.remove_goal(goal.id))
        self.assertNotIn(goal.id, agent.goals)

    def test_reorder_queue(self):
        agent = self.make_agent()
        first, second = agent.add_goal("first"), agent.add_goal("second")
        self.assertTrue(agent.reorder_queue(second.id, 0))
        self.assertEqual(agent.run_next().id, second.id)

    def test_goal_dependencies_delay_execution(self):
        agent = self.make_agent()
        first = agent.add_goal("first")
        second = agent.add_goal("second", dependencies=[first.id])
        self.assertEqual(agent.run_next().id, first.id)
        self.assertEqual(agent.run_next().id, second.id)

    def test_sensitive_goal_requires_approval(self):
        agent = self.make_agent()
        goal = agent.add_goal("delete a file")
        agent.run_goal(goal.id)
        self.assertEqual(goal.status, ExecutionState.WAITING_APPROVAL)

    def test_sensitive_goal_runs_when_approved(self):
        agent = self.make_agent(approval_callback=lambda goal: True)
        goal = agent.add_goal("delete a file")
        agent.run_goal(goal.id)
        self.assertEqual(goal.status, ExecutionState.COMPLETED)

    def test_failed_verification_retries_and_fails(self):
        executor = FakeExecutor(output="I couldn't find a clear answer from the internet right now.")
        agent = self.make_agent(planner=FakePlanner([Task(id="search", description="search", capability="Internet")]), executor=executor, retry_limit=1)
        goal = agent.add_goal("search")
        agent.run_goal(goal.id)
        self.assertEqual(goal.status, ExecutionState.FAILED)
        self.assertEqual(executor.calls, 2)

    def test_execution_history_records_transitions(self):
        agent = self.make_agent()
        goal = agent.add_goal("do work")
        agent.run_goal(goal.id)
        self.assertGreaterEqual(len(goal.execution_history), 3)

    def test_inspect_project_reports_standard_project_files(self):
        result = self.make_agent().inspect_project(".")
        self.assertTrue(result["readme"])
        self.assertTrue(result["tests"])

    def test_background_worker_completes_queued_goal(self):
        agent = self.make_agent()
        goal = agent.add_goal("do work", start=True)
        for _ in range(20):
            if goal.status == ExecutionState.COMPLETED:
                break
            time.sleep(0.02)
        agent.stop()
        self.assertEqual(goal.status, ExecutionState.COMPLETED)

    def test_brain_exposes_project_agent_progress(self):
        brain = EchoBrain()
        goal = brain.submit_project_goal("do work", background=False)
        progress = brain.get_progress(goal.id)
        self.assertEqual(progress["current_goal"], goal.id)
        self.assertEqual(progress["remaining_tasks"], 0)


if __name__ == "__main__":
    unittest.main()
