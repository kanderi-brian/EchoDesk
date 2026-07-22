from typing import Any, Dict

from .manager import MemoryManager
from .retrieval import MemoryRetrieval
from .search import MemorySearch


class MemoryController:
    """Public interface to EchoDesk memory subsystem."""

    def __init__(
        self,
        manager: MemoryManager,
        retrieval: MemoryRetrieval,
        search_service: MemorySearch,
    ) -> None:
        self.manager = manager
        self.retrieval = retrieval
        self.search_service = search_service

    def remember(self, key: str, value: Any, category: str = "general") -> Dict[str, Any]:
        return self.manager.remember(key, value, category)

    def recall(self, key: str) -> Dict[str, Any]:
        return self.manager.recall(key)

    def forget(self, key: str) -> Dict[str, Any]:
        return self.manager.forget(key)

    def update(self, key: str, value: Any) -> Dict[str, Any]:
        return self.manager.update_memory(key, value)

    def exists(self, key: str) -> Dict[str, Any]:
        return self.manager.memory_exists(key)

    def list_memories(self) -> Dict[str, Any]:
        return self.manager.list_memories()

    def latest(self, limit: int = 10) -> Dict[str, Any]:
        return self.retrieval.latest(limit)

    def search(self, query: str) -> Dict[str, Any]:
        return self.search_service.search(query)

    def search_keys(self, query: str) -> Dict[str, Any]:
        return self.search_service.search_keys(query)

    def search_values(self, query: str) -> Dict[str, Any]:
        return self.search_service.search_values(query)

    def search_category(self, category: str) -> Dict[str, Any]:
        return self.search_service.search_category(category)
