from typing import Any, Dict, Iterable, List

from .manager import MemoryManager


class MemoryRetrieval:
    """Retrieval layer for EchoDesk memory through MemoryManager."""

    def __init__(self, manager: MemoryManager) -> None:
        self.manager = manager

    def retrieve(self, key: str) -> Dict[str, Any]:
        if not isinstance(key, str) or not key.strip():
            return self._error("retrieve", "Memory key must be a non-empty string.")

        return self.manager.recall(key.strip())

    def retrieve_many(self, keys: Iterable[str]) -> Dict[str, Any]:
        if not isinstance(keys, Iterable) or isinstance(keys, (str, bytes)):
            return self._error("retrieve_many", "Keys must be an iterable of strings.")

        key_list = list(keys)
        if not key_list:
            return self._success(
                "retrieve_many",
                "Memory records retrieved.",
                result={"records": []},
            )

        for key in key_list:
            if not isinstance(key, str) or not key.strip():
                return self._error("retrieve_many", "Each memory key must be a non-empty string.")

        found_records: List[Dict[str, Any]] = []
        for key in key_list:
            result = self.manager.recall(key.strip())
            if result.get("success") and result.get("result"):
                found_records.append(result["result"]["record"])

        return self._success(
            "retrieve_many",
            "Memory records retrieved.",
            result={"records": found_records},
        )

    def retrieve_by_category(self, category: str) -> Dict[str, Any]:
        if not isinstance(category, str) or not category.strip():
            return self._error("retrieve_by_category", "Category must be a non-empty string.")

        list_result = self.manager.list_memories()
        if not list_result.get("success"):
            return list_result

        records = list_result.get("result", {}).get("records", [])
        filtered = [record for record in records if record.get("category") == category.strip()]

        return self._success(
            "retrieve_by_category",
            "Memory records retrieved by category.",
            result={"records": filtered},
        )

    def latest(self, limit: int = 10) -> Dict[str, Any]:
        if not isinstance(limit, int) or limit <= 0:
            return self._error("latest", "Limit must be a positive integer.")

        list_result = self.manager.list_memories()
        if not list_result.get("success"):
            return list_result

        records = list_result.get("result", {}).get("records", [])
        sorted_records = sorted(
            records,
            key=lambda record: record.get("updated_at", ""),
            reverse=True,
        )
        limited = sorted_records[:limit]

        return self._success(
            "latest",
            "Latest memory records retrieved.",
            result={"records": limited},
        )

    def exists(self, key: str) -> Dict[str, Any]:
        if not isinstance(key, str) or not key.strip():
            return self._error("exists", "Memory key must be a non-empty string.")

        return self.manager.memory_exists(key.strip())

    def _success(self, action: str, message: str, result: Dict[str, Any] | None = None) -> Dict[str, Any]:
        response: Dict[str, Any] = {"success": True, "action": action, "message": message}
        if result is not None:
            response["result"] = result
        return response

    def _error(self, action: str, message: str, details: Any = None) -> Dict[str, Any]:
        response: Dict[str, Any] = {"success": False, "action": action, "message": message}
        if details is not None:
            response["details"] = details
        return response
