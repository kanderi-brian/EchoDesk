import logging
from typing import List


class Plugin:
    """Base class for plugins.

    Provide safe defaults so existing functionality is optional.
    """

    name: str = "base"
    description: str = "Base plugin"
    version: str = "0.0.1"
    author: str = "EchoDesk"
    capabilities: List[str] = []

    # New metadata
    priority: int = 100
    enabled: bool = True
    permissions: List[str] = []
    dependencies: List[str] = []
    api_version: str = "1"
    entry_point: str = ""

    def __init__(self):
        self.logger = logging.getLogger(f"echodesk.plugin.{self.name}")

    def initialize(self) -> None:
        """Called when plugin is loaded. Safe default does nothing."""
        self.logger.debug("initialize called for %s", self.name)

    def shutdown(self) -> None:
        """Called when plugin is unloaded. Safe default does nothing."""
        self.logger.debug("shutdown called for %s", self.name)

    def can_handle(self, command: str) -> bool:
        """Whether this plugin can handle a command.

        Default: False
        """
        return False

    def execute(self, command: str):
        """Execute the command and return a result.

        Default: returns None
        """
        self.logger.debug("execute called for %s with command: %s", self.name, command)
        return None

    def hooks(self) -> dict:
        """Optional integration declarations for EchoBrain subsystems.

        Plugins should prefer the explicit ``configure_*`` methods for setup;
        this empty mapping keeps older plugins free of integration concerns.
        """
        return {}

    def configure_agents(self, registry) -> None:
        """Optionally register specialist agents.  Default is a no-op."""

    def configure_planner(self, planner) -> None:
        """Optionally configure planner-facing extensions.  Default is a no-op."""

    def configure_learning(self, learning_engine) -> None:
        """Optionally configure learning-facing extensions.  Default is a no-op."""

    def configure_brain(self, brain) -> None:
        """Optionally configure EchoBrain after all services are available."""
