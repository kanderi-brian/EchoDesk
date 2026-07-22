import unittest
from unittest.mock import Mock

from memory.controller import MemoryController


class TestMemoryController(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = Mock()
        self.retrieval = Mock()
        self.search_service = Mock()
        self.controller = MemoryController(self.manager, self.retrieval, self.search_service)

    def test_remember_delegates_to_manager(self):
        self.manager.remember.return_value = {"success": True, "action": "remember"}

        result = self.controller.remember("note", "content", category="general")

        self.assertTrue(result["success"])
        self.manager.remember.assert_called_once_with("note", "content", "general")

    def test_recall_delegates_to_manager(self):
        self.manager.recall.return_value = {"success": True, "action": "recall"}

        result = self.controller.recall("note")

        self.assertTrue(result["success"])
        self.manager.recall.assert_called_once_with("note")

    def test_forget_delegates_to_manager(self):
        self.manager.forget.return_value = {"success": True, "action": "forget"}

        result = self.controller.forget("note")

        self.assertTrue(result["success"])
        self.manager.forget.assert_called_once_with("note")

    def test_update_delegates_to_manager(self):
        self.manager.update_memory.return_value = {"success": True, "action": "update_memory"}

        result = self.controller.update("note", "updated")

        self.assertTrue(result["success"])
        self.manager.update_memory.assert_called_once_with("note", "updated")

    def test_exists_delegates_to_manager(self):
        self.manager.memory_exists.return_value = {"success": True, "action": "memory_exists"}

        result = self.controller.exists("note")

        self.assertTrue(result["success"])
        self.manager.memory_exists.assert_called_once_with("note")

    def test_list_memories_delegates_to_manager(self):
        self.manager.list_memories.return_value = {"success": True, "action": "list_memories"}

        result = self.controller.list_memories()

        self.assertTrue(result["success"])
        self.manager.list_memories.assert_called_once()

    def test_latest_delegates_to_retrieval(self):
        self.retrieval.latest.return_value = {"success": True, "action": "latest"}

        result = self.controller.latest(limit=5)

        self.assertTrue(result["success"])
        self.retrieval.latest.assert_called_once_with(5)

    def test_search_delegates_to_search(self):
        self.search_service.search.return_value = {"success": True, "action": "search"}

        result = self.controller.search("query")

        self.assertTrue(result["success"])
        self.search_service.search.assert_called_once_with("query")

    def test_search_keys_delegates_to_search(self):
        self.search_service.search_keys.return_value = {"success": True, "action": "search_keys"}

        result = self.controller.search_keys("query")

        self.assertTrue(result["success"])
        self.search_service.search_keys.assert_called_once_with("query")

    def test_search_values_delegates_to_search(self):
        self.search_service.search_values.return_value = {"success": True, "action": "search_values"}

        result = self.controller.search_values("query")

        self.assertTrue(result["success"])
        self.search_service.search_values.assert_called_once_with("query")

    def test_search_category_delegates_to_search(self):
        self.search_service.search_category.return_value = {"success": True, "action": "search_category"}

        result = self.controller.search_category("personal")

        self.assertTrue(result["success"])
        self.search_service.search_category.assert_called_once_with("personal")

    def test_invalid_input_propagation(self):
        self.manager.recall.return_value = {"success": False, "action": "recall", "message": "Invalid key."}

        result = self.controller.recall(123)  # type: ignore[arg-type]

        self.assertFalse(result["success"])
        self.manager.recall.assert_called_once_with(123)


if __name__ == "__main__":
    unittest.main()
