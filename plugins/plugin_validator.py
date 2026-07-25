"""Validation for independent plugin metadata and dependencies."""
from __future__ import annotations
import re
from .base_plugin import PluginMetadata


class PluginValidator:
    API_VERSION = "1"
    def validate_metadata(self, metadata: PluginMetadata) -> tuple[bool, str]:
        if not isinstance(metadata.name, str) or not metadata.name.strip(): return False, "Plugin name is required."
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", metadata.name): return False, "Plugin name contains invalid characters."
        if not isinstance(metadata.version, str) or not metadata.version.strip(): return False, "Plugin version is required."
        if not isinstance(metadata.author, str) or not isinstance(metadata.description, str): return False, "Plugin author and description must be strings."
        if metadata.api_version != self.API_VERSION: return False, "Incompatible plugin API version."
        if not isinstance(metadata.permissions, list) or not isinstance(metadata.dependencies, list): return False, "Permissions and dependencies must be lists."
        if any(not isinstance(item, str) or not item.strip() for item in metadata.permissions + metadata.dependencies): return False, "Permissions and dependencies must contain non-empty strings."
        if len(set(metadata.dependencies)) != len(metadata.dependencies): return False, "Plugin dependencies must be unique."
        if metadata.entry_point and not isinstance(metadata.entry_point, str): return False, "Plugin entry point must be a string."
        return True, "valid"
    def validate_dependencies(self, name: str, dependencies: list[str], installed: set[str]) -> tuple[bool, str]:
        if name in dependencies: return False, "A plugin cannot depend on itself."
        missing = [item for item in dependencies if item not in installed]
        return (False, f"Missing plugin dependencies: {', '.join(missing)}") if missing else (True, "valid")
