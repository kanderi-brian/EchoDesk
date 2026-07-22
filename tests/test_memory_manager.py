import unittest
from unittest.mock import Mock

from memory.manager import MemoryManager


class TestMemoryManager(unittest.TestCase):
    def setUp(self) -> None:
        self.storage = Mock()
        self.manager = MemoryManager(self.storage)

    def test_remember_new_memory_saves_record(self):
        self.storage.get.return_value = {
            "success": False,
            "action": "get",
            "message": "Memory record not found.",
        }
        self.storage.save.return_value = {
            "success": True,
            "action": "save",
            "message": "Memory record saved.",
            "result": {"record": {"key": "note", "value": "read book"}},
        }

        result = self.manager.remember("note", "read book", category="personal")

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "remember")
        self.assertEqual(result["result"]["record"]["key"], "note")
        self.storage.get.assert_called_once_with("note")
        self.storage.save.assert_called_once_with("note", "read book", "personal")

    def test_remember_existing_memory_updates_record(self):
        self.storage.get.return_value = {
            "success": True,
            "action": "get",
            "message": "Memory record retrieved.",
            "result": {"record": {"key": "note", "value": "read book"}},
        }
        self.storage.update.return_value = {
            "success": True,
            "action": "update",
            "message": "Memory record updated.",
        }

        result = self.manager.remember("note", "finish book")

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "remember")
        self.assertEqual(result["message"], "Memory updated.")
        self.storage.get.assert_called_once_with("note")
        self.storage.update.assert_called_once_with("note", "finish book")
        self.storage.save.assert_not_called()

    def test_recall_returns_storage_result(self):
        self.storage.get.return_value = {
            "success": True,
            "action": "get",
            "message": "Memory record retrieved.",
            "result": {"record": {"key": "note", "value": "read book"}},
        }

        result = self.manager.recall("note")

        self.assertTrue(result["success"])
        self.assertEqual(result["result"]["record"]["key"], "note")
        self.storage.get.assert_called_once_with("note")

    def test_forget_deletes_memory(self):
        self.storage.delete.return_value = {
            "success": True,
            "action": "delete",
            "message": "Memory record deleted.",
        }

        result = self.manager.forget("note")

        self.assertTrue(result["success"])
        self.storage.delete.assert_called_once_with("note")

    def test_update_memory_delegates_to_storage(self):
        self.storage.update.return_value = {
            "success": True,
            "action": "update",
            "message": "Memory record updated.",
        }

        result = self.manager.update_memory("note", "finish book")

        self.assertTrue(result["success"])
        self.storage.update.assert_called_once_with("note", "finish book")

    def test_list_memories_delegates_to_storage(self):
        self.storage.list_all.return_value = {
            "success": True,
            "action": "list_all",
            "message": "Memory records listed.",
            "result": {"records": []},
        }

        result = self.manager.list_memories()

        self.assertTrue(result["success"])
        self.storage.list_all.assert_called_once()

    def test_memory_exists_returns_true_when_found(self):
        self.storage.get.return_value = {
            "success": True,
            "action": "get",
            "message": "Memory record retrieved.",
            "result": {"record": {"key": "note", "value": "read book"}},
        }

        result = self.manager.memory_exists("note")

        self.assertTrue(result["success"])
        self.assertTrue(result["result"]["exists"])
        self.storage.get.assert_called_once_with("note")

    def test_memory_exists_returns_false_when_not_found(self):
        self.storage.get.return_value = {
            "success": False,
            "action": "get",
            "message": "Memory record not found.",
        }

        result = self.manager.memory_exists("note")

        self.assertTrue(result["success"])
        self.assertFalse(result["result"]["exists"])
        self.storage.get.assert_called_once_with("note")

    def test_remember_invalid_key_returns_error(self):
        result = self.manager.remember("", "value")

        self.assertFalse(result["success"])
        self.storage.get.assert_not_called()

    def test_update_memory_invalid_value_returns_error(self):
        result = self.manager.update_memory("note", None)

        self.assertFalse(result["success"])
        self.storage.update.assert_not_called()


if __name__ == "__main__":
    unittest.main()
