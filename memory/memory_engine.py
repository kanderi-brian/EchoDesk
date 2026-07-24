"""Memory engine module for EchoDesk."""


class MemoryEngine:
    """A lightweight long-term memory engine placeholder."""

    def remember(self, key: str, value: str) -> dict[str, str]:
        """Return a minimal response for storing a memory."""
        return {"status": "not_implemented", "key": key, "value": value}

    def recall(self, query: str) -> dict[str, str]:
        """Return a minimal response for recalling memory."""
        return {"status": "not_implemented", "query": query}
