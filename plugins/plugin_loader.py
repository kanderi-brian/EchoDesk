"""Metadata file discovery without granting code execution privileges."""
from __future__ import annotations
import json
from pathlib import Path
from .base_plugin import PluginMetadata


class PluginLoader:
    METADATA_FILE = "plugin.json"
    def read_metadata(self, directory: str | Path) -> PluginMetadata | None:
        path = Path(directory) / self.METADATA_FILE
        if not path.is_file(): return None
        try:
            return PluginMetadata(**json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return None
