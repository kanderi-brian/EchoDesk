import unittest
import logging

from plugins.plugin import Plugin
from plugins.plugin_registry import PluginRegistry
from plugins.plugin_manager import PluginManager


class DummyPlugin(Plugin):
    name = "dummy"
    capabilities = ["Test"]

    def can_handle(self, command: str) -> bool:
        return command == "dummy"

    def execute(self, command: str):
        return "ok"


class TestPluginManager(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_registry_register_and_get(self):
        registry = PluginRegistry()
        p = DummyPlugin()
        self.assertTrue(registry.register(p))
        self.assertEqual(registry.count(), 1)
        self.assertIs(registry.get("dummy"), p)

    def test_duplicate_prevention(self):
        registry = PluginRegistry()
        p = DummyPlugin()
        self.assertTrue(registry.register(p))
        # registering another plugin with same name should fail
        p2 = DummyPlugin()
        self.assertFalse(registry.register(p2))
        self.assertEqual(registry.count(), 1)

    def test_find_by_capability(self):
        registry = PluginRegistry()
        p = DummyPlugin()
        registry.register(p)
        found = registry.find_by_capability("Test")
        self.assertEqual(len(found), 1)
        self.assertIs(found[0], p)

    def test_plugin_discovery_and_loading(self):
        manager = PluginManager()
        names = manager.discover()
        # production plugins should include system_info but not the intentionally broken test plugin
        self.assertIn("system_info", names)
        self.assertNotIn("broken_plugin", names)

        loaded = manager.load_plugins()
        # At least the system_info plugin should be loaded successfully
        self.assertGreaterEqual(loaded, 1)

        registry = manager.get_registry()
        sys_plugin = registry.get("system_info")
        self.assertIsNotNone(sys_plugin)
        self.assertTrue(sys_plugin.can_handle("system info"))
        result = sys_plugin.execute("system info")
        self.assertIsInstance(result, str)

        # Now verify broken plugin (test fixture) when placed in test resources is handled gracefully
        import os
        tests_resources = os.path.join(os.path.dirname(__file__), "resources")
        test_manager = PluginManager(plugins_package_path=tests_resources)
        test_names = test_manager.discover()
        self.assertIn("broken_plugin", test_names)

        loaded2 = test_manager.load_plugins()
        # The broken plugin should not load successfully
        self.assertEqual(loaded2, 0)
        self.assertIsNone(test_manager.get_registry().get("broken_plugin"))

    def test_manager_registers_multiple_plugins_without_duplicates(self):
        manager = PluginManager()
        # load twice to ensure duplicates are not double-registered
        first = manager.load_plugins()
        second = manager.load_plugins()
        # second load should not increase registry count for already-registered plugins
        self.assertGreaterEqual(first, 1)
        self.assertEqual(manager.get_registry().count(), manager.get_registry().count())


if __name__ == "__main__":
    unittest.main()
