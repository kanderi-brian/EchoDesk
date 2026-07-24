import unittest
import uuid

from plugins.plugin import Plugin
from plugins.plugin_manager import PluginManager
from plugins.plugin_registry import PluginRegistry
from planner.planner import PlannerEngine, ExecutionPlan, Task
from executor.task_executor import TaskExecutor
from brain.brain import EchoBrain


class SysPlugin(Plugin):
    name = "sys"
    capabilities = ["System"]

    def can_handle(self, command: str) -> bool:
        return command.strip().lower() in ("system info", "computer info", "pc info")

    def execute(self, command: str):
        return "system-ok"


class FailingPlugin(Plugin):
    name = "fail"
    capabilities = ["System"]

    def can_handle(self, command: str) -> bool:
        return command.strip().lower() == "will fail"

    def execute(self, command: str):
        raise RuntimeError("boom")


class PriorityPlugin(Plugin):
    def __init__(self, name, priority):
        self.name = name
        self.priority = priority
        self.capabilities = ["Test"]

    def can_handle(self, command: str) -> bool:
        return command.strip().lower() == "do thing"

    def execute(self, command: str):
        return f"handled by {self.name}"


class TestPhase16_3(unittest.TestCase):
    def test_planner_routes_plugin_commands(self):
        registry = PluginRegistry()
        registry.register(SysPlugin())
        planner = PlannerEngine()
        planner.set_plugin_registry(registry)

        plan = planner.plan("system info")
        self.assertIsInstance(plan, ExecutionPlan)
        self.assertTrue(plan.tasks)
        self.assertEqual(plan.tasks[0].capability, "Plugin")

    def test_priority_selection_and_disabled(self):
        registry = PluginRegistry()
        p1 = PriorityPlugin("p1", 20)
        p2 = PriorityPlugin("p2", 1)
        registry.register(p1)
        registry.register(p2)
        # both support
        handlers = registry.get_handlers("do thing")
        self.assertEqual(handlers[0].name, "p2")

        # disable p2
        handlers[0].enabled = False
        h2 = registry.find_handler("do thing")
        self.assertEqual(h2.name, "p1")

    def test_reload_and_shutdown_plugins(self):
        pm = PluginManager()
        # register a plugin instance directly
        pm.get_registry().register(SysPlugin())
        self.assertGreater(pm.get_registry().count(), 0)
        pm.shutdown_plugins()
        self.assertEqual(pm.get_registry().count(), 0)
        # reload should repopulate (from production plugins)
        loaded = pm.reload_plugins()
        self.assertGreaterEqual(loaded, 1)

    def test_plugin_execution_and_failure(self):
        pm = PluginManager()
        pm.get_registry().register(SysPlugin())
        pm.get_registry().register(FailingPlugin())

        executor = TaskExecutor(plugin_manager=pm)
        # success case
        plan = ExecutionPlan(goal="system info")
        plan.add_task(Task(id=str(uuid.uuid4()), description="Run plugin", capability="Plugin"))
        res = executor.execute_plan(plan, "system info")
        self.assertEqual(res.status, "SUCCESS")
        self.assertIn("system-ok", res.final_response)

        # failure case
        plan2 = ExecutionPlan(goal="will fail")
        plan2.add_task(Task(id=str(uuid.uuid4()), description="Run plugin", capability="Plugin"))
        res2 = executor.execute_plan(plan2, "will fail")
        self.assertEqual(res2.status, "FAILED")

    def test_planner_fallback_when_no_plugin(self):
        planner = PlannerEngine()
        # no plugin registry set
        plan = planner.plan("system info")
        # planner previously didn't support system info, expect None or not Plugin
        if plan is not None:
            self.assertNotIn("Plugin", plan.required_capabilities)

    def test_brain_reload_command(self):
        brain = EchoBrain()
        resp = brain.process("reload plugins")
        self.assertIsInstance(resp, str)
        self.assertTrue(resp.lower().startswith("reloaded"))


if __name__ == "__main__":
    unittest.main()
