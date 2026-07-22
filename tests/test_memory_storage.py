import gc
import os
import sqlite3
import tempfile
import unittest

from memory.storage import MemoryStorage


class TestMemoryStorage(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_memory.db")
        self.storage = MemoryStorage(db_path=self.db_path)

    def tearDown(self) -> None:
        self.storage = None
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_initialize_creates_database_and_table(self):
        result = self.storage.initialize()

        self.assertTrue(result["success"])
        self.assertTrue(os.path.exists(self.db_path))

        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memory_records'")
        row = cursor.fetchone()
        connection.close()

        self.assertIsNotNone(row)

    def test_save_and_get_memory_record(self):
        self.storage.initialize()

        save_result = self.storage.save("favorite_color", "blue", category="personal")
        self.assertTrue(save_result["success"])
        self.assertEqual(save_result["result"]["record"]["key"], "favorite_color")

        get_result = self.storage.get("favorite_color")
        self.assertTrue(get_result["success"])
        self.assertEqual(get_result["result"]["record"]["value"], "blue")
        self.assertEqual(get_result["result"]["record"]["category"], "personal")

    def test_update_changes_existing_record(self):
        self.storage.initialize()
        self.storage.save("goal", "learn python")

        update_result = self.storage.update("goal", "learn advanced python")
        self.assertTrue(update_result["success"])

        get_result = self.storage.get("goal")
        self.assertTrue(get_result["success"])
        self.assertEqual(get_result["result"]["record"]["value"], "learn advanced python")

    def test_delete_removes_record(self):
        self.storage.initialize()
        self.storage.save("session", "active")

        delete_result = self.storage.delete("session")
        self.assertTrue(delete_result["success"])

        get_result = self.storage.get("session")
        self.assertFalse(get_result["success"])
        self.assertIn("not found", get_result["message"].lower())

    def test_list_all_returns_records(self):
        self.storage.initialize()
        self.storage.save("one", "1")
        self.storage.save("two", "2")

        list_result = self.storage.list_all()
        self.assertTrue(list_result["success"])
        records = list_result["result"]["records"]
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["key"], "one")
        self.assertEqual(records[1]["key"], "two")

    def test_save_invalid_key_returns_error(self):
        self.storage.initialize()

        result = self.storage.save("", "value")
        self.assertFalse(result["success"])
        self.assertIn("non-empty string", result["message"])

    def test_save_none_value_returns_error(self):
        self.storage.initialize()

        result = self.storage.save("key", None)
        self.assertFalse(result["success"])
        self.assertIn("cannot be None", result["message"])

    def test_update_nonexistent_record_returns_error(self):
        self.storage.initialize()

        result = self.storage.update("missing", "value")
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"].lower())

    def test_delete_nonexistent_record_returns_error(self):
        self.storage.initialize()

        result = self.storage.delete("missing")
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"].lower())


if __name__ == "__main__":
    unittest.main()
