from pathlib import Path
from ..plugin import Plugin


class FileToolsPlugin(Plugin):
    name = "file_tools"
    description = "Lists files in the current workspace without changing them."
    version = "1.0.0"
    capabilities = ["Files"]
    permissions = ["filesystem_read"]

    def can_handle(self, command: str) -> bool:
        return command.strip().casefold() in {"list files", "workspace files", "file count"}

    def execute(self, command: str) -> str:
        files = sorted(item.name for item in Path.cwd().iterdir())
        if command.strip().casefold() == "file count":
            return f"The workspace contains {len(files)} top-level items."
        return "Workspace items: " + (", ".join(files[:30]) if files else "none")
