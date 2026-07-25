"""Read-only repository status commands."""
from __future__ import annotations
import subprocess
from pathlib import Path
from ..plugin import Plugin


class GitPlugin(Plugin):
    name = "git"
    description = "Reports the current Git repository status without modifying it."
    version = "1.0.0"
    capabilities = ["Git"]
    permissions = ["filesystem_read", "process_control"]

    def can_handle(self, command: str) -> bool:
        return command.strip().casefold() in {"git status", "repository status", "repo status"}

    def execute(self, command: str) -> str:
        root = Path.cwd()
        if not (root / ".git").exists():
            return "No Git repository is available in the current workspace."
        result = subprocess.run(["git", "status", "--short"], cwd=root, capture_output=True, text=True, timeout=10, check=False)
        if result.returncode:
            return f"Git status is unavailable: {result.stderr.strip() or 'unknown error'}"
        return result.stdout.strip() or "Working tree is clean."
