"""Regression coverage for Phase 19 plugin lifecycle behavior."""
from __future__ import annotations
import unittest

from plugins.plugin import Plugin
from plugins.plugin_manager import PluginManager
from plugins.plugin_permissions import PluginPermissions
from plugins.plugin_validator import PluginValidator
from plugins.base_plugin import PluginMetadata


class DependencyPlugin(Plugin):
    capabilities = ["Test"]
    def __init__(self, name: str, dependencies: list[str] | None = None):
        super().__init__()
        self.name = name
        self.dependencies = dependencies or []
        self.initialized = 0
        self.stopped = 0
    def initialize(self): self.initialized += 1
    def shutdown(self): self.stopped += 1
    def can_handle(self, command: str) -> bool: return command == self.name
    def execute(self, command: str): return f"ran:{self.name}"


class RestrictedPlugin(DependencyPlugin):
    permissions = ["filesystem_write"]


class HookPlugin(DependencyPlugin):
    def __init__(self):
        super().__init__("hook")
        self.called = []
    def configure_agents(self, registry): self.called.append("agents")
    def configure_planner(self, planner): self.called.append("planner")
    def configure_learning(self, learning): self.called.append("learning")
    def configure_brain(self, brain): self.called.append("brain")


class TestPhase19Plugins(unittest.TestCase):
    def test_batch_install_resolves_reverse_order_dependencies(self):
        manager = PluginManager()
        child, parent = DependencyPlugin("child", ["parent"]), DependencyPlugin("parent")
        self.assertEqual(manager.install_many([child, parent]), 2)
        self.assertEqual(child.initialized, 1)

    def test_missing_and_cyclic_dependencies_are_rejected(self):
        manager = PluginManager()
        self.assertEqual(manager.install_many([DependencyPlugin("missing", ["nope"])]), 0)
        self.assertEqual(manager.install_many([DependencyPlugin("one", ["two"]), DependencyPlugin("two", ["one"])]), 0)

    def test_lifecycle_respects_dependents(self):
        manager = PluginManager()
        parent, child = DependencyPlugin("parent"), DependencyPlugin("child", ["parent"])
        manager.install_many([child, parent])
        self.assertFalse(manager.disable("parent"))
        self.assertFalse(manager.uninstall("parent"))
        self.assertTrue(manager.disable("child"))
        self.assertTrue(manager.disable("parent"))
        self.assertFalse(manager.enable("child"))
        self.assertTrue(manager.enable("parent"))
        self.assertTrue(manager.enable("child"))
        self.assertTrue(manager.uninstall("child"))
        self.assertTrue(manager.uninstall("parent"))

    def test_update_preserves_old_plugin_when_new_metadata_is_invalid(self):
        manager = PluginManager()
        old = DependencyPlugin("versioned")
        self.assertTrue(manager.install(old))
        replacement = DependencyPlugin("versioned")
        replacement.api_version = "99"
        self.assertFalse(manager.update(replacement))
        self.assertIs(manager.get_registry().get("versioned"), old)

    def test_permissions_are_checked_at_execution_time_and_logged(self):
        manager = PluginManager(permissions=PluginPermissions(granted=[]))
        plugin = RestrictedPlugin("restricted")
        self.assertTrue(manager.install(plugin))
        denied = manager.execute("restricted")
        self.assertFalse(denied["success"])
        self.assertEqual(manager.get_execution_log()[-1]["error"], "permission_denied")
        self.assertTrue(manager.permissions.grant("filesystem_write"))
        self.assertEqual(manager.execute("restricted"), "ran:restricted")

    def test_integration_hooks_and_builtin_discovery(self):
        manager = PluginManager()
        hook = HookPlugin()
        self.assertTrue(manager.install(hook))
        planner = type("Planner", (), {"set_plugin_registry": lambda self, registry: setattr(self, "registry", registry)})()
        manager.integrate(brain=object(), agent_registry=object(), planner=planner, learning_engine=object())
        self.assertEqual(hook.called, ["agents", "planner", "learning", "brain"])
        self.assertIs(planner.registry, manager.get_registry())
        discovered = set(PluginManager().discover())
        self.assertTrue({"system_info", "git", "github", "calendar", "file_tools"}.issubset(discovered))

    def test_metadata_validation_rejects_invalid_declarations(self):
        manager = PluginManager()
        invalid = DependencyPlugin("bad name")
        self.assertFalse(manager.install(invalid))
        invalid = DependencyPlugin("duplicates", ["same", "same"])
        self.assertFalse(manager.install(invalid))


# These generated, independently named cases keep the permission and metadata
# boundary matrix visible in unittest output without introducing a test helper
# dependency into the application.
def _grant_case(permission):
    def test(self):
        permissions = PluginPermissions(granted=[])
        self.assertTrue(permissions.grant(permission))
        self.assertTrue(permissions.allows([permission]))
    return test


def _revoke_case(permission):
    def test(self):
        permissions = PluginPermissions(granted=[permission])
        permissions.revoke(permission)
        self.assertFalse(permissions.allows([permission]))
    return test


def _builtin_route_case(plugin_name, command):
    def test(self):
        manager = PluginManager()
        self.assertEqual(manager.load_plugins(), 5)
        plugin = manager.get_registry().get(plugin_name)
        self.assertIsNotNone(plugin)
        self.assertTrue(plugin.can_handle(command))
    return test


def _builtin_metadata_case(plugin_name):
    def test(self):
        manager = PluginManager()
        self.assertEqual(manager.load_plugins(), 5)
        plugin = manager.get_registry().get(plugin_name)
        self.assertTrue(manager.validate(plugin))
    return test


def _invalid_name_case(name):
    def test(self):
        valid, _ = PluginValidator().validate_metadata(PluginMetadata(name=name))
        self.assertFalse(valid)
    return test


for _permission in sorted(PluginPermissions.ALLOWED):
    setattr(TestPhase19Plugins, f"test_grant_{_permission}", _grant_case(_permission))
    setattr(TestPhase19Plugins, f"test_revoke_{_permission}", _revoke_case(_permission))

for _plugin_name, _command in (
    ("system_info", "system info"), ("git", "git status"),
    ("github", "github help"), ("calendar", "calendar today"),
    ("file_tools", "list files"),
):
    setattr(TestPhase19Plugins, f"test_builtin_route_{_plugin_name}", _builtin_route_case(_plugin_name, _command))
    setattr(TestPhase19Plugins, f"test_builtin_metadata_{_plugin_name}", _builtin_metadata_case(_plugin_name))

for _index, _invalid_name in enumerate(("", " ", "bad name", "bad/name", "bad\\name", "bad:name", "-prefix", ".prefix", "@name", "name!")):
    setattr(TestPhase19Plugins, f"test_invalid_metadata_name_{_index}", _invalid_name_case(_invalid_name))


def _test_known_permission_rejects_unknown(self):
    self.assertFalse(PluginPermissions(granted=[]).grant("not_a_permission"))


def _test_execution_log_is_copied(self):
    manager = PluginManager()
    manager.install(DependencyPlugin("logged"))
    manager.execute("logged")
    entries = manager.get_execution_log()
    entries[0]["plugin"] = "changed"
    self.assertEqual(manager.get_execution_log()[0]["plugin"], "logged")


def _test_registry_ignores_disabled_capability(self):
    manager = PluginManager()
    manager.install(DependencyPlugin("disabled"))
    manager.disable("disabled")
    self.assertEqual(manager.get_registry().find_by_capability("Test"), [])


TestPhase19Plugins.test_known_permission_rejects_unknown = _test_known_permission_rejects_unknown
TestPhase19Plugins.test_execution_log_is_copied = _test_execution_log_is_copied
TestPhase19Plugins.test_registry_ignores_disabled_capability = _test_registry_ignores_disabled_capability
