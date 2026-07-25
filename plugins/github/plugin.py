"""Safe GitHub command assistance; no credentials or network calls."""
from ..plugin import Plugin


class GitHubPlugin(Plugin):
    name = "github"
    description = "Provides safe GitHub workflow guidance."
    version = "1.0.0"
    capabilities = ["GitHub"]
    dependencies = ["git"]

    def can_handle(self, command: str) -> bool:
        return command.strip().casefold() in {"github help", "github status", "github workflow"}

    def execute(self, command: str) -> str:
        return "GitHub integration is available for repository workflows. Use 'git status' to inspect the local repository first."
