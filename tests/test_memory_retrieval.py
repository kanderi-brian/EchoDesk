import unittest
from unittest.mock import Mock

from memory.retrieval import MemoryRetrieval


class TestMemoryRetrieval(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = Mock()
        self.retrieval = MemoryRetrieval(self.manager)

    def test_retrieve_returns_manager_recall_result(self):
        self.manager.recall.return_value = {
            "success": True,
            "action": "recall",
            "message": "Memory record retrieved.",
            "result": {"record": {"key": "note", "value": "read book"}},
        }

        result = self.retrieval.retrieve("note")

        self.assertTrue(result["success"])
        self.assertEqual(result["result"]["record"]["key"], "note")
        self.manager.recall.assert_called_once_with("note")

    def test_retrieve_invalid_key_returns_error(self):
        result = self.retrieval.retrieve(123)  # type: ignore[arg-type]

        self.assertFalse(result["success"])
        self.assertIn("non-empty string", result["message"])
        self.manager.recall.assert_not_called()

    def test_retrieve_many_returns_only_found_records(self):
        self.manager.recall.side_effect = [
            {
                "success": True,
                "result": {"record": {"key": "a", "value": "1"}},
            },
            {
                "success": False,
                "action": "recall",
                "message": "Memory record not found.",
            },
            {
                "success": True,
                "result": {"record": {"key": "c", "value": "3"}},
            },
        ]

        result = self.retrieval.retrieve_many(["a", "b", "c"])

        self.assertTrue(result["success"])
        self.assertEqual(len(result["result"]["records"]), 2)
        self.assertEqual(result["result"]["records"][0]["key"], "a")
        self.assertEqual(result["result"]["records"][1]["key"], "c")
        self.assertEqual(self.manager.recall.call_count, 3)

    def test_retrieve_many_invalid_keys_returns_error(self):
        result = self.retrieval.retrieve_many(["a", "", "c"])

        self.assertFalse(result["success"])
        self.manager.recall.assert_not_called()

    def test_retrieve_by_category_filters_records(self):
        self.manager.list_memories.return_value = {
            "success": True,
            "action": "list_all",
            "message": "Memory records listed.",
            "result": {
                "records": [
                    {"key": "a", "value": "1", "category": "work"},
                    {"key": "b", "value": "2", "category": "personal"},
                    {"key": "c", "value": "3", "category": "work"},
                ]
            },
        }

        result = self.retrieval.retrieve_by_category("work")

        self.assertTrue(result["success"])
        self.assertEqual(len(result["result"]["records"]), 2)
        self.manager.list_memories.assert_called_once()

    def test_retrieve_by_category_invalid_category_returns_error(self):
        result = self.retrieval.retrieve_by_category(123)  # type: ignore[arg-type]

        self.assertFalse(result["success"])
        self.manager.list_memories.assert_not_called()

    def test_latest_returns_sorted_records(self):
        self.manager.list_memories.return_value = {
            "success": True,
            "result": {
                "records": [
                    {"key": "a", "updated_at": "2026-07-22T18:00:00+00:00"},
                    {"key": "b", "updated_at": "2026-07-22T19:00:00+00:00"},
                    {"key": "c", "updated_at": "2026-07-22T17:00:00+00:00"},
                ]
            },
        }

        result = self.retrieval.latest(limit=2)

        self.assertTrue(result["success"])
        self.assertEqual(len(result["result"]["records"]), 2)
        self.assertEqual(result["result"]["records"][0]["key"], "b")
        self.assertEqual(result["result"]["records"][1]["key"], "a")
        self.manager.list_memories.assert_called_once()

    def test_latest_invalid_limit_returns_error(self):
        result = self.retrieval.latest(0)

        self.assertFalse(result["success"])
        self.manager.list_memories.assert_not_called()

    def test_exists_delegates_to_manager(self):
        self.manager.memory_exists.return_value = {
            "success": True,
            "action": "memory_exists",
            "result": {"exists": True},
        }

        result = self.retrieval.exists("note")

        self.assertTrue(result["success"])
        self.manager.memory_exists.assert_called_once_with("note")

    def test_exists_invalid_key_returns_error(self):
        result = self.retrieval.exists(123)  # type: ignore[arg-type]

        self.assertFalse(result["success"])
        self.manager.memory_exists.assert_not_called()


if __name__ == "__main__":
    unittest.main()
