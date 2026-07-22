from typing import Any, Dict

from .storage import MemoryStorage


class MemoryManager:
    """Business logic layer for EchoDesk memory operations."""

    def __init__(self, storage: MemoryStorage) -> None:
        self.storage = storage

    def remember(self, key: str, value: Any, category: str = "general") -> Dict[str, Any]:
        if not isinstance(key, str) or not key.strip():
            return self._error("remember", "Memory key must be a non-empty string.")

        if value is None:
            return self._error("remember", "Memory value cannot be None.")

        key = key.strip()
        existing = self.storage.get(key)

        if existing.get("success"):
            update_result = self.storage.update(key, value)
            if update_result.get("success"):
                return self._success(
                    "remember",
                    "Memory updated.",
                    result={"record": {"key": key, "value": str(value)}},
                )
            return update_result

        if existing.get("action") == "get" and "not found" in existing.get("message", "").lower():
            save_result = self.storage.save(key, value, category)
            if save_result.get("success"):
                return self._success(
                    "remember",
                    "Memory saved.",
                    result={"record": save_result.get("result", {}).get("record")},
                )
            return save_result

        return existing

    def recall(self, key: str) -> Dict[str, Any]:
        if not isinstance(key, str) or not key.strip():
            return self._error("recall", "Memory key must be a non-empty string.")

        return self.storage.get(key.strip())

    def forget(self, key: str) -> Dict[str, Any]:
        if not isinstance(key, str) or not key.strip():
            return self._error("forget", "Memory key must be a non-empty string.")

        return self.storage.delete(key.strip())

    def update_memory(self, key: str, value: Any) -> Dict[str, Any]:
        if not isinstance(key, str) or not key.strip():
            return self._error("update_memory", "Memory key must be a non-empty string.")

        if value is None:
            return self._error("update_memory", "Memory value cannot be None.")

        return self.storage.update(key.strip(), value)

    def list_memories(self) -> Dict[str, Any]:
        return self.storage.list_all()

    def memory_exists(self, key: str) -> Dict[str, Any]:
        if not isinstance(key, str) or not key.strip():
            return self._error("memory_exists", "Memory key must be a non-empty string.")

        result = self.storage.get(key.strip())
        if result.get("success"):
            return self._success("memory_exists", "Memory exists.", result={"exists": True})

        if result.get("action") == "get" and "not found" in result.get("message", "").lower():
            return self._success("memory_exists", "Memory does not exist.", result={"exists": False})

        return result

    def _success(self, action: str, message: str, result: Dict[str, Any] | None = None) -> Dict[str, Any]:
        response = {"success": True, "action": action, "message": message}
        if result is not None:
            response["result"] = result
        return response

    def _error(self, action: str, message: str, details: Any = None) -> Dict[str, Any]:
        response = {"success": False, "action": action, "message": message}
        if details is not None:
            response["details"] = details
        return response
