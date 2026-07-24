import unittest
import os

from plugins.plugin import Plugin
from plugins.plugin_manager import PluginManager
from plugins.plugin_registry import PluginRegistry
from executor.task_executor import TaskExecutor, ExecutionResult
from planner.planner import ExecutionPlan, Task


class DummyPlugin(Plugin):
    name = "dummy_exec"
    description = "Dummy executor"
    capabilities = ["Test"]

    def can_handle(self, command: str) -> bool:
        return command.strip().lower() == "do dummy"

    def execute(self, command: str):
        return "dummy-result"


class DummyPlugin2(Plugin):
    name = "dummy2"
    capabilities = ["Test", "Extra"]

    def can_handle(self, command: str) -> bool:
        return command.strip().lower() == "do other"

    def execute(self, command: str):
        return "dummy2-result"


class TestPluginInvocation(unittest.TestCase):
    def test_registry_find_and_supports(self):
        registry = PluginRegistry()
        p = DummyPlugin()
        registry.register(p)
        self.assertTrue(registry.supports("do dummy"))
        handler = registry.find_handler("do dummy")
        self.assertIsNotNone(handler)
        self.assertEqual(handler.name, "dummy_exec")

    def test_find_handlers_by_capability(self):
        registry = PluginRegistry()
        registry.register(DummyPlugin())
        registry.register(DummyPlugin2())
        found = registry.find_handlers("Test")
        self.assertEqual(len(found), 2)
        found_extra = registry.find_handlers("Extra")
        self.assertEqual(len(found_extra), 1)

    def test_taskexecutor_plugin_handling(self):
        # Create a PluginManager pointing to the plugins folder and register a dummy plugin
        pm = PluginManager()
        # avoid filesystem discovery; register directly
        pm.get_registry().register(DummyPlugin())

        executor = TaskExecutor(plugin_manager=pm)

        # Create plan with a single task (capability doesn't matter because plugin will handle by command)
        plan = ExecutionPlan(goal="do dummy")
        plan.add_task(Task(id="1", description="Run plugin", capability="System"))

        result = executor.execute_plan(plan, "do dummy")
        self.assertIsInstance(result, ExecutionResult)
        self.assertIn("dummy-result", result.final_response)

    def test_plugin_fallback_to_engines(self):
        pm = PluginManager()
        executor = TaskExecutor(plugin_manager=pm)
        # No plugin handles this; create a task with unsupported capability
        plan = ExecutionPlan(goal="unknown")
        plan.add_task(Task(id="1", description="Unknown", capability="NoSuchCapability"))
        result = executor.execute_plan(plan, "unknown")
        # Should mark task as failed
        self.assertEqual(result.status, "FAILED")


if __name__ == "__main__":
    unittest.main()
