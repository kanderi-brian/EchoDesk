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
