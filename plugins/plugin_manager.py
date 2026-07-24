import importlib
import inspect
import logging
import os
import pkgutil
from typing import List

from .plugin import Plugin
from .plugin_registry import PluginRegistry


class PluginManager:
    """Discover, instantiate and register plugins found under the 'plugins' package."""

    def __init__(self, plugins_package_path: str = None):
        self.logger = logging.getLogger("echodesk.plugin_manager")
        self.registry = PluginRegistry()
        # Determine filesystem path for plugins package
        if plugins_package_path:
            self.plugins_path = plugins_package_path
        else:
            # assume package is importable as 'plugins'
            try:
                import plugins as _pkg

                self.plugins_path = os.path.dirname(_pkg.__file__)
            except Exception:
                # fallback to relative path
                self.plugins_path = os.path.join(os.getcwd(), "plugins")

    def discover(self) -> List[str]:
        """Discover top-level plugin packages inside plugins/ directory."""
        found = []
        try:
            for finder, name, ispkg in pkgutil.iter_modules([self.plugins_path]):
                # ignore core plugin package files
                if name in {"__pycache__", "plugin", "plugin_manager", "plugin_registry"}:
                    continue
                found.append(name)
        except Exception:
            self.logger.exception("Plugin discovery failed")
        return found

    def load_plugins(self) -> int:
        """Discover and load plugin modules, instantiate Plugin subclasses and register them."""
        loaded = 0
        names = self.discover()
        for name in names:
            full_pkg = f"plugins.{name}"
            # try to import plugin module inside package: plugins.<name>.plugin
            module_name = f"{full_pkg}.plugin"
            try:
                module = importlib.import_module(module_name)
            except Exception:
                self.logger.exception("Failed to import plugin module %s", module_name)
                continue

            # find classes that inherit from Plugin
            for _, obj in inspect.getmembers(module, inspect.isclass):
                try:
                    if obj is Plugin:
                        continue
                    if issubclass(obj, Plugin):
                        try:
                            instance = obj()
                        except Exception:
                            self.logger.exception("Failed to instantiate plugin class %s in %s", obj, module_name)
                            continue

                        # register
                        try:
                            registered = self.registry.register(instance)
                            if registered:
                                try:
                                    instance.initialize()
                                except Exception:
                                    self.logger.exception("Plugin %s initialize failed", instance.name)
                                loaded += 1
                            else:
                                self.logger.warning("Plugin %s not registered (duplicate?)", instance.name)
                        except Exception:
                            self.logger.exception("Error registering plugin %s", getattr(instance, "name", str(instance)))
                except Exception:
                    self.logger.exception("Error while inspecting module %s for plugins", module_name)
        return loaded

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
                try:
                    p.shutdown()
                except Exception:
                    self.logger.exception("Plugin %s shutdown failed", getattr(p, "name", str(p)))
            # clear registry
            self.registry = PluginRegistry()
            self.logger.info("Shutdown all plugins and cleared registry")
        except Exception:
            self.logger.exception("Failed during shutdown_plugins")

    def get_registry(self) -> PluginRegistry:
        return self.registry
