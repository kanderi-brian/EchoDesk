import logging
from typing import Dict, List, Optional

from .plugin import Plugin


class PluginRegistry:
    """Registry to manage plugin instances."""

    def __init__(self):
        self._plugins: Dict[str, Plugin] = {}
        self.logger = logging.getLogger("echodesk.plugin_registry")

    def register(self, plugin: Plugin) -> bool:
        """Register a plugin instance. Returns True if registered, False if duplicate."""
        name = str(getattr(plugin, "name", "")).strip()
        if not name:
            self.logger.warning("Attempt to register a plugin without a name")
            return False
        if name in self._plugins:
            self.logger.warning("Plugin with name '%s' already registered", plugin.name)
            return False

        self._plugins[name] = plugin
        self.logger.info("Registered plugin '%s'", name)
        return True

    def unregister(self, plugin_name: str) -> bool:
        """Unregister a plugin by name. Returns True if removed."""
        if plugin_name not in self._plugins:
            self.logger.warning("Attempt to unregister unknown plugin '%s'", plugin_name)
            return False

        try:
            plugin = self._plugins.pop(plugin_name)
            try:
                plugin.shutdown()
            except Exception:
                self.logger.exception("Error shutting down plugin '%s'", plugin_name)
            self.logger.info("Unregistered plugin '%s'", plugin_name)
            return True
        except Exception:
            self.logger.exception("Failed to unregister plugin '%s'", plugin_name)
            return False

    def get(self, plugin_name: str) -> Optional[Plugin]:
        return self._plugins.get(plugin_name)

    def get_all(self) -> List[Plugin]:
        return list(self._plugins.values())

    def find_by_capability(self, capability: str, enabled_only: bool = True) -> List[Plugin]:
        result = []
        for p in self._plugins.values():
            try:
                if (not enabled_only or getattr(p, "enabled", True)) and capability in getattr(p, "capabilities", []):
                    result.append(p)
            except Exception:
                self.logger.exception("Error checking capabilities for plugin '%s'", getattr(p, "name", "?"))
        return result

    def get_enabled_plugins(self) -> List[Plugin]:
        """Return list of enabled plugin instances."""
        return [p for p in self._plugins.values() if getattr(p, "enabled", True)]

    def get_handlers(self, command: str) -> List[Plugin]:
        """Return all enabled plugins that can handle the command, sorted by priority ascending."""
        handlers: List[Plugin] = []
        for p in self.get_enabled_plugins():
            try:
                if hasattr(p, "can_handle") and p.can_handle(command):
                    handlers.append(p)
            except Exception:
                self.logger.exception("Error while asking plugin '%s' if it can handle command", getattr(p, "name", "?"))
        # sort by priority (lower value wins)
        handlers.sort(key=lambda x: getattr(x, "priority", 100))
        return handlers

    def find_handler(self, command: str) -> Optional[Plugin]:
        """Return the highest-priority plugin that can handle the given command."""
        handlers = self.get_handlers(command)
        return handlers[0] if handlers else None

    def find_handlers(self, capability: str) -> List[Plugin]:
        """Alias for find_by_capability (plural)."""
        return self.find_by_capability(capability)

    def dependents_of(self, plugin_name: str) -> List[Plugin]:
        """Return registered plugins that declare a dependency on ``plugin_name``."""
        return [
            plugin for plugin in self._plugins.values()
            if plugin_name in getattr(plugin, "dependencies", [])
        ]

    def supports(self, command: str) -> bool:
        """Return True if any registered and enabled plugin can handle the command."""
        return bool(self.get_handlers(command))

    def count(self) -> int:
        return len(self._plugins)
