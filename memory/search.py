from typing import Any, Dict, List

from .retrieval import MemoryRetrieval


class MemorySearch:
    """Search layer for EchoDesk memory through MemoryRetrieval."""

    def __init__(self, retrieval: MemoryRetrieval) -> None:
        self.retrieval = retrieval

    def search(self, query: str) -> Dict[str, Any]:
        if not isinstance(query, str) or not query.strip():
            return self._error("search", "Search query must be a non-empty string.")

        all_records_result = self._all_records()
        if not all_records_result.get("success"):
            return all_records_result

        query_lower = query.strip().lower()
        matched = [
            record
            for record in all_records_result["result"]["records"]
            if query_lower in str(record.get("key", "")).lower()
            or query_lower in str(record.get("value", "")).lower()
        ]

        return self._success("search", "Memory search completed.", result={"records": matched})

    def search_keys(self, query: str) -> Dict[str, Any]:
        if not isinstance(query, str) or not query.strip():
            return self._error("search_keys", "Search query must be a non-empty string.")

        all_records_result = self._all_records()
        if not all_records_result.get("success"):
            return all_records_result

        query_lower = query.strip().lower()
        matched = [
            record
            for record in all_records_result["result"]["records"]
            if query_lower in str(record.get("key", "")).lower()
        ]

        return self._success("search_keys", "Memory key search completed.", result={"records": matched})

    def search_values(self, query: str) -> Dict[str, Any]:
        if not isinstance(query, str) or not query.strip():
            return self._error("search_values", "Search query must be a non-empty string.")

        all_records_result = self._all_records()
        if not all_records_result.get("success"):
            return all_records_result

        query_lower = query.strip().lower()
        matched = [
            record
            for record in all_records_result["result"]["records"]
            if query_lower in str(record.get("value", "")).lower()
        ]

        return self._success("search_values", "Memory value search completed.", result={"records": matched})

    def search_category(self, category: str) -> Dict[str, Any]:
        if not isinstance(category, str) or not category.strip():
            return self._error("search_category", "Category must be a non-empty string.")

        return self.retrieval.retrieve_by_category(category.strip())

    def _all_records(self) -> Dict[str, Any]:
        return self.retrieval.latest(limit=1000000)

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
