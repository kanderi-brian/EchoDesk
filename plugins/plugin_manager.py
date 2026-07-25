import importlib
import importlib.util
import inspect
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, List

from .plugin import Plugin
from .plugin_registry import PluginRegistry
from .base_plugin import PluginMetadata
from .plugin_loader import PluginLoader
from .plugin_permissions import PluginPermissions
from .plugin_validator import PluginValidator


class PluginManager:
    """Discover, instantiate and register plugins found under the 'plugins' package."""

    def __init__(self, plugins_package_path: str = None, permissions: PluginPermissions | None = None):
        self.logger = logging.getLogger("echodesk.plugin_manager")
        self.registry = PluginRegistry()
        self.permissions = permissions or PluginPermissions()
        self.validator = PluginValidator()
        self.loader = PluginLoader()
        self.metadata: dict[str, PluginMetadata] = {}
        self.execution_log: list[dict[str, Any]] = []
        self.learning_engine: Any | None = None
        if not self.logger.handlers:
            os.makedirs("logs", exist_ok=True)
            handler = logging.FileHandler(os.path.join("logs", "plugins.log"), encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        # Determine filesystem path for plugins package
        if plugins_package_path:
            self.plugins_path = os.path.abspath(plugins_package_path)
        else:
            # assume package is importable as 'plugins'
            try:
                import plugins as _pkg

                self.plugins_path = os.path.dirname(_pkg.__file__)
            except Exception:
                # fallback to relative path
                self.plugins_path = os.path.join(os.getcwd(), "plugins")

    def discover(self) -> List[str]:
        """Discover plugin directories without importing their implementation."""
        found: list[str] = []
        try:
            ignored = {"__pycache__", "plugin", "plugin_manager", "plugin_registry", "base_plugin", "plugin_loader", "plugin_validator", "plugin_permissions", "sample_plugins"}
            for entry in Path(self.plugins_path).iterdir():
                if entry.name in ignored or entry.name.startswith("."):
                    continue
                if entry.is_dir() and (entry / "plugin.py").is_file():
                    found.append(entry.name)
        except Exception:
            self.logger.exception("Plugin discovery failed")
        return sorted(found)

    def discover_metadata(self) -> dict[str, PluginMetadata]:
        """Return valid optional ``plugin.json`` declarations without importing code."""
        discovered: dict[str, PluginMetadata] = {}
        for name in self.discover():
            directory = Path(self.plugins_path) / name
            metadata_path = directory / self.loader.METADATA_FILE
            if not metadata_path.exists():
                continue
            metadata = self.loader.read_metadata(directory)
            if metadata is None:
                self.logger.warning("Ignoring plugin %s: invalid metadata file", name)
                continue
            valid, reason = self.validator.validate_metadata(metadata)
            if not valid or not self.permissions.validate(metadata.permissions):
                self.logger.warning("Ignoring plugin %s: %s", name, reason)
                continue
            discovered[name] = metadata
        return discovered

    def load_plugins(self) -> int:
        """Discover and load plugin modules, instantiate Plugin subclasses and register them."""
        candidates: list[Plugin] = []
        for name in self.discover():
            directory = Path(self.plugins_path) / name
            metadata_path = directory / self.loader.METADATA_FILE
            declared = self.loader.read_metadata(directory) if metadata_path.exists() else None
            if metadata_path.exists() and declared is None:
                self.logger.warning("Ignoring plugin %s: invalid metadata file", name)
                continue
            if declared is not None:
                valid, reason = self.validator.validate_metadata(declared)
                if not valid or not self.permissions.validate(declared.permissions):
                    self.logger.warning("Ignoring plugin %s: %s", name, reason)
                    continue
            try:
                module = self._load_module(name)
            except Exception:
                self.logger.exception("Failed to import plugin module for %s", name)
                continue
            for _, obj in inspect.getmembers(module, inspect.isclass):
                try:
                    if obj is Plugin:
                        continue
                    if issubclass(obj, Plugin):
                        try:
                            instance = obj()
                            if declared is not None and declared.name != instance.name:
                                self.logger.warning("Ignoring plugin %s: metadata name does not match implementation", name)
                                continue
                            candidates.append(instance)
                        except Exception:
                            self.logger.exception("Failed to instantiate plugin class %s", obj)
                except Exception:
                    self.logger.exception("Error while inspecting plugin module %s", name)
        return self.install_many(candidates)

    def install(self, plugin: Plugin, initialize: bool = True) -> bool:
        """Validate and register an in-process plugin; no code is copied or executed here."""
        metadata = self._metadata_for(plugin)
        valid, reason = self.validator.validate_metadata(metadata)
        if not valid or not self.permissions.validate(metadata.permissions):
            self.logger.warning("Rejected plugin %s: %s", metadata.name, reason)
            return False
        valid, reason = self.validator.validate_dependencies(metadata.name, metadata.dependencies, {item.name for item in self.registry.get_all()})
        if not valid:
            self.logger.warning("Rejected plugin %s: %s", metadata.name, reason)
            return False
        if not self.registry.register(plugin):
            return False
        self.metadata[metadata.name] = metadata
        if initialize:
            try:
                plugin.initialize()
            except Exception:
                self.registry.unregister(metadata.name)
                self.metadata.pop(metadata.name, None)
                self.logger.exception("Plugin %s initialization failed", metadata.name)
                return False
        self.logger.info("Installed plugin %s", metadata.name)
        return True

    def install_many(self, plugins: list[Plugin]) -> int:
        """Install a batch in dependency order, independent of directory order."""
        pending = {str(getattr(plugin, "name", "")): plugin for plugin in plugins}
        loaded = 0
        while pending:
            progress = False
            for name, plugin in list(pending.items()):
                installed = {item.name for item in self.registry.get_all()}
                metadata = self._metadata_for(plugin)
                valid, reason = self.validator.validate_metadata(metadata)
                if not valid or not self.permissions.validate(metadata.permissions):
                    self.logger.warning("Rejected plugin %s: %s", name, reason)
                    pending.pop(name)
                    progress = True
                    continue
                missing = [dep for dep in metadata.dependencies if dep not in installed and dep not in pending]
                if missing:
                    self.logger.warning("Rejected plugin %s: missing dependencies %s", name, ", ".join(missing))
                    pending.pop(name)
                    progress = True
                    continue
                if all(dep in installed for dep in metadata.dependencies):
                    if self.install(plugin):
                        loaded += 1
                    pending.pop(name)
                    progress = True
            if not progress:
                self.logger.warning("Unresolvable plugin dependencies: %s", ", ".join(sorted(pending)))
                break
        return loaded

    def validate(self, plugin: Plugin) -> bool:
        metadata = self._metadata_for(plugin)
        return self.validator.validate_metadata(metadata)[0] and self.permissions.validate(metadata.permissions)

    def enable(self, name: str) -> bool:
        plugin = self.registry.get(name)
        if not plugin: return False
        dependencies = list(getattr(plugin, "dependencies", []))
        if any(self.registry.get(dep) is None or not getattr(self.registry.get(dep), "enabled", True) for dep in dependencies):
            self.logger.warning("Cannot enable %s because a dependency is unavailable", name)
            return False
        plugin.enabled = True; self.logger.info("Enabled plugin %s", name); return True

    def disable(self, name: str) -> bool:
        plugin = self.registry.get(name)
        if not plugin: return False
        if any(getattr(item, "enabled", True) for item in self.registry.dependents_of(name)):
            self.logger.warning("Cannot disable %s while enabled dependents exist", name)
            return False
        plugin.enabled = False; self.logger.info("Disabled plugin %s", name); return True

    def uninstall(self, name: str) -> bool:
        if self.registry.dependents_of(name):
            self.logger.warning("Cannot uninstall %s while dependents exist", name)
            return False
        self.metadata.pop(name, None)
        removed = self.registry.unregister(name)
        if removed: self.logger.info("Uninstalled plugin %s", name)
        return removed

    remove = uninstall
    unload = uninstall

    def update(self, plugin: Plugin) -> bool:
        name = plugin.name
        old = self.registry.get(name)
        if old is None:
            return self.install(plugin)
        # Validate first, preserving the working instance on a rejected update.
        if not self.validate(plugin):
            return False
        dependents = self.registry.dependents_of(name)
        if dependents:
            self.logger.warning("Cannot update %s while dependents exist", name)
            return False
        self.uninstall(name)
        if self.install(plugin):
            return True
        self.install(old)
        return False

    def list_plugins(self) -> list[dict[str, object]]:
        return [{"name": plugin.name, "enabled": bool(getattr(plugin, "enabled", True)), "version": getattr(plugin, "version", ""), "permissions": list(getattr(plugin, "permissions", [])), "capabilities": list(getattr(plugin, "capabilities", []))} for plugin in self.registry.get_all()]

    def execute(self, command: str):
        """Execute only an enabled handler whose declared permissions are granted."""
        plugin = self.registry.find_handler(command)
        if plugin is None: return None
        if not self.permissions.allows(list(getattr(plugin, "permissions", []))):
            self.logger.warning("Permission denied plugin=%s", plugin.name)
            self._record_execution(plugin.name, command, False, "permission_denied")
            return {"success": False, "message": "Plugin permissions were not granted."}
        try:
            result = plugin.execute(command)
            self.logger.info("Executed plugin %s", plugin.name)
            self._record_execution(plugin.name, command, True)
            return result
        except Exception as exc:
            self._record_execution(plugin.name, command, False, str(exc))
            self.logger.exception("Plugin execution failed: %s", plugin.name)
            raise

    def get_execution_log(self, limit: int | None = None) -> list[dict[str, Any]]:
        entries = self.execution_log if limit is None else self.execution_log[-max(0, limit):]
        return [dict(item) for item in entries]

    def _record_execution(self, plugin: str, command: str, success: bool, error: str = "") -> None:
        self.execution_log.append({"timestamp": time.time(), "plugin": plugin, "command": command, "success": success, "error": error})
        self.execution_log = self.execution_log[-500:]
        self.logger.info("plugin_execution plugin=%s success=%s", plugin, success)
        if self.learning_engine is not None:
            try:
                self.learning_engine.record_outcome(
                    f"plugin:{plugin}", success, workflow="plugin_execution",
                    failure=error,
                )
            except Exception:
                self.logger.debug("Plugin learning event could not be recorded", exc_info=True)

    def integrate(self, *, brain: Any | None = None, agent_registry: Any | None = None,
                  planner: Any | None = None, learning_engine: Any | None = None) -> None:
        """Attach optional plugin hooks after the host services are constructed."""
        self.learning_engine = learning_engine
        if planner is not None:
            planner.set_plugin_registry(self.registry)
        for plugin in self.registry.get_all():
            try:
                if agent_registry is not None:
                    plugin.configure_agents(agent_registry)
                if planner is not None:
                    plugin.configure_planner(planner)
                if learning_engine is not None:
                    plugin.configure_learning(learning_engine)
                if brain is not None:
                    plugin.configure_brain(brain)
            except Exception:
                self.logger.exception("Plugin integration hook failed: %s", plugin.name)

    @staticmethod
    def _metadata_for(plugin: Plugin) -> PluginMetadata:
        return PluginMetadata(plugin.name, getattr(plugin, "version", "0.0.1"), getattr(plugin, "author", ""), getattr(plugin, "description", ""), list(getattr(plugin, "permissions", [])), list(getattr(plugin, "dependencies", [])), getattr(plugin, "api_version", "1"), getattr(plugin, "entry_point", ""))

    def reload_plugins(self) -> int:
        """Shutdown and reload plugins from disk.

        Returns the number of plugins loaded after reload.
        """
        try:
            self.shutdown_plugins()
            # clear registry and reload
            self.registry = PluginRegistry()
            loaded = self.load_plugins()
            self.logger.info("Reloaded plugins: %d", loaded)
            return loaded
        except Exception:
            self.logger.exception("Failed to reload plugins")
            return 0

    def shutdown_plugins(self) -> None:
        """Shutdown all registered plugins and clear registry."""
        try:
            for p in list(self.registry.get_all()):
                self.registry.unregister(p.name)
            self.registry = PluginRegistry()
            self.metadata.clear()
            self.logger.info("Shutdown all plugins and cleared registry")
        except Exception:
            self.logger.exception("Failed during shutdown_plugins")

    def get_registry(self) -> PluginRegistry:
        return self.registry

    def _load_module(self, name: str):
        """Load bundled modules normally and external plugin folders by path."""
        default_path = os.path.abspath(os.path.dirname(__file__))
        if os.path.abspath(self.plugins_path) == default_path:
            return importlib.import_module(f"plugins.{name}.plugin")
        module_path = Path(self.plugins_path) / name / "plugin.py"
        module_name = f"echodesk_external_plugin_{name}_{abs(hash(str(module_path)))}"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load plugin module {module_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
