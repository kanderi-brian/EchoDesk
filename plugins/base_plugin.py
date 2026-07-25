"""Phase 19 plugin base and declarative metadata."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from .plugin import Plugin


@dataclass
class PluginMetadata:
    name: str
    version: str = "0.0.1"
    author: str = "EchoDesk"
    description: str = ""
    permissions: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    api_version: str = "1"
    entry_point: str = ""


class BasePlugin(Plugin):
    """Backward-compatible plugin with metadata and declared permissions."""
    permissions: list[str] = []
    dependencies: list[str] = []
    api_version: str = "1"
    entry_point: str = ""

    def metadata(self) -> PluginMetadata:
        return PluginMetadata(self.name, self.version, self.author, self.description, list(self.permissions), list(self.dependencies), self.api_version, self.entry_point)

    def hooks(self) -> dict[str, list[Any]]:
        """Optional extension points; plugins return registrations, not internals."""
        return {}
