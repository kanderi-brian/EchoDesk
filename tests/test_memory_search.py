import unittest
from unittest.mock import Mock

from memory.search import MemorySearch


class TestMemorySearch(unittest.TestCase):
    def setUp(self) -> None:
        self.retrieval = Mock()
        self.search = MemorySearch(self.retrieval)

    def test_search_matches_key_or_value_case_insensitive(self):
        self.retrieval.latest.return_value = {
            "success": True,
            "result": {
                "records": [
                    {"key": "Note", "value": "Read Book", "category": "personal"},
                    {"key": "Task", "value": "Write report", "category": "work"},
                ]
            },
        }

        result = self.search.search("read")

        self.assertTrue(result["success"])
        self.assertEqual(len(result["result"]["records"]), 1)
        self.assertEqual(result["result"]["records"][0]["key"], "Note")

    def test_search_partial_matching(self):
        self.retrieval.latest.return_value = {
            "success": True,
            "result": {
                "records": [
                    {"key": "shopping", "value": "Buy milk"},
                    {"key": "appointment", "value": "Doctor"},
                ]
            },
        }

        result = self.search.search("shop")

        self.assertTrue(result["success"])
        self.assertEqual(len(result["result"]["records"]), 1)
        self.assertEqual(result["result"]["records"][0]["key"], "shopping")

    def test_search_keys_only(self):
        self.retrieval.latest.return_value = {
            "success": True,
            "result": {
                "records": [
                    {"key": "Note", "value": "Read Book"},
                    {"key": "Task", "value": "Note something"},
                ]
            },
        }

        result = self.search.search_keys("note")

        self.assertTrue(result["success"])
        self.assertEqual(len(result["result"]["records"]), 1)
        self.assertEqual(result["result"]["records"][0]["key"], "Note")

    def test_search_values_only(self):
        self.retrieval.latest.return_value = {
            "success": True,
            "result": {
                "records": [
                    {"key": "Note", "value": "Read Book"},
                    {"key": "Task", "value": "Note something"},
                ]
            },
        }

        result = self.search.search_values("note")

        self.assertTrue(result["success"])
        self.assertEqual(len(result["result"]["records"]), 1)
        self.assertEqual(result["result"]["records"][0]["key"], "Task")

    def test_search_category_uses_retrieval_by_category(self):
        self.retrieval.retrieve_by_category.return_value = {
            "success": True,
            "result": {"records": [{"key": "note", "category": "personal"}]},
        }

        result = self.search.search_category("personal")

        self.assertTrue(result["success"])
        self.retrieval.retrieve_by_category.assert_called_once_with("personal")

    def test_search_invalid_query_returns_error(self):
        result = self.search.search("")

        self.assertFalse(result["success"])
        self.retrieval.latest.assert_not_called()

    def test_search_keys_invalid_query_returns_error(self):
        result = self.search.search_keys("  ")

        self.assertFalse(result["success"])
        self.retrieval.latest.assert_not_called()

    def test_search_values_invalid_query_returns_error(self):
        result = self.search.search_values(None)  # type: ignore[arg-type]

        self.assertFalse(result["success"])
        self.retrieval.latest.assert_not_called()

    def test_search_category_invalid_returns_error(self):
        result = self.search.search_category(123)  # type: ignore[arg-type]

        self.assertFalse(result["success"])
        self.retrieval.retrieve_by_category.assert_not_called()

    def test_search_propagates_retrieval_failure(self):
        self.retrieval.latest.return_value = {
            "success": False,
            "action": "latest",
            "message": "Failed to list memories.",
        }

        result = self.search.search("note")

        self.assertFalse(result["success"])
        self.assertEqual(result["action"], "latest")


if __name__ == "__main__":
    unittest.main()
