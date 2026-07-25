"""Regression tests for the Phase 17 collaboration framework."""
import time
import unittest

from agents import AgentContext, AgentRegistry, AgentResult, AgentScheduler, AgentTask, BaseAgent, PlannerAgent


class FakeAgent(BaseAgent):
    name = "fake"
    def execute(self, task, context):
        context.set(task.description, task.payload.get("value", task.description))
        if task.payload.get("sleep"):
            time.sleep(task.payload["sleep"])
        return AgentResult(task.id, self.name, not task.payload.get("fail", False), output=task.description, confidence=.9, verification={"success": not task.payload.get("fail", False)})


class TestAgents(unittest.TestCase):
    def setUp(self):
        self.registry = AgentRegistry()
        self.agent = self.registry.register(FakeAgent())
        self.context = AgentContext(current_goal="test goal")

    def test_registry_lifecycle(self):
        self.assertIs(self.registry.get("fake"), self.agent)
        self.assertTrue(self.registry.unregister("fake"))
        self.assertIsNone(self.registry.get("fake"))

    def test_context_records_completion(self):
        task = AgentTask("work", "fake")
        result = self.agent.run(task, self.context)
        self.assertIn(task.id, self.context.completed_tasks)
        self.assertTrue(result.success)

    def test_scheduler_resolves_dependency(self):
        first, second = AgentTask("first", "fake"), AgentTask("second", "fake")
        second.dependencies = [first.id]
        results = AgentScheduler(self.registry).run([second, first], self.context)
        self.assertTrue(results[second.id].success)

    def test_scheduler_retries_failure(self):
        task = AgentTask("fail", "fake", payload={"fail": True}, max_retries=1)
        result = AgentScheduler(self.registry).run([task], self.context)[task.id]
        self.assertFalse(result.success)
        self.assertEqual(task.retries, 1)

    def test_scheduler_rejects_circular_task(self):
        task = AgentTask("bad", "fake")
        task.dependencies = [task.id]
        with self.assertRaises(ValueError):
            AgentScheduler(self.registry).run([task])

    def test_parallel_execution(self):
        tasks = [AgentTask(str(index), "fake", payload={"sleep": .01}) for index in range(3)]
        self.assertEqual(len(AgentScheduler(self.registry).run(tasks, self.context, parallel=True)), 3)

    def test_planner_conflict_resolution_prefers_verification(self):
        planner = PlannerAgent()
        weak = AgentResult("1", "one", True, confidence=.99, verification={"success": False})
        strong = AgentResult("2", "two", True, confidence=.2, verification={"success": True})
        self.assertIs(planner.resolve_conflict([weak, strong], self.context), strong)


def _make_task_case(index):
    def test(self):
        task = AgentTask(f"task {index}", "fake", priority=index, payload={"value": index})
        result = AgentScheduler(self.registry).run([task], self.context)[task.id]
        self.assertTrue(result.success)
        self.assertEqual(self.context.get(f"task {index}"), index)
    return test


# Independent task messages cover priority values and structured context writes.
for _index in range(1, 44):
    setattr(TestAgents, f"test_structured_task_{_index:02d}", _make_task_case(_index))
