import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import MemoryRecord


class MemoryStorage:
    """Persistent storage for EchoDesk memory records."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or "memory.db"
        self._initialized = False

    def initialize(self) -> Dict[str, Any]:
        try:
            path = Path(self.db_path)
            if not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)

            with closing(sqlite3.connect(self.db_path)) as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS memory_records (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            key TEXT NOT NULL UNIQUE,
                            value TEXT NOT NULL,
                            category TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL
                        )
                        """
                    )
                    connection.commit()
                finally:
                    cursor.close()

            self._initialized = True
            return self._success("initialize", "Memory storage initialized.")
        except Exception as exc:
            return self._error("initialize", "Failed to initialize memory storage.", details=str(exc))

    def save(self, key: str, value: Any, category: str = "general") -> Dict[str, Any]:
        if not isinstance(key, str) or not key.strip():
            return self._error("save", "Memory key must be a non-empty string.")

        if value is None:
            return self._error("save", "Memory value cannot be None.")

        if not self._initialized:
            init_result = self.initialize()
            if not init_result.get("success"):
                return init_result

        try:
            record = MemoryRecord.create(key.strip(), str(value), category or "general")
            with closing(sqlite3.connect(self.db_path)) as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "INSERT INTO memory_records (key, value, category, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                        (record.key, record.value, record.category, record.created_at, record.updated_at),
                    )
                    connection.commit()
                    record.id = cursor.lastrowid
                finally:
                    cursor.close()
            return self._success("save", "Memory record saved.", result={"record": record.__dict__})
        except sqlite3.IntegrityError:
            return self._error("save", "Memory key already exists. Use update() to modify existing records.")
        except Exception as exc:
            return self._error("save", "Failed to save memory record.", details=str(exc))

    def get(self, key: str) -> Dict[str, Any]:
        if not isinstance(key, str) or not key.strip():
            return self._error("get", "Memory key must be a non-empty string.")

        if not self._initialized:
            init_result = self.initialize()
            if not init_result.get("success"):
                return init_result

        try:
            with closing(sqlite3.connect(self.db_path)) as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "SELECT id, key, value, category, created_at, updated_at FROM memory_records WHERE key = ?",
                        (key.strip(),),
                    )
                    row = cursor.fetchone()
                finally:
                    cursor.close()
            if row is None:
                return self._error("get", "Memory record not found.", details=key.strip())

            record = MemoryRecord(*row)
            return self._success("get", "Memory record retrieved.", result={"record": record.__dict__})
        except Exception as exc:
            return self._error("get", "Failed to retrieve memory record.", details=str(exc))

    def update(self, key: str, value: Any) -> Dict[str, Any]:
        if not isinstance(key, str) or not key.strip():
            return self._error("update", "Memory key must be a non-empty string.")

        if value is None:
            return self._error("update", "Memory value cannot be None.")

        if not self._initialized:
            init_result = self.initialize()
            if not init_result.get("success"):
                return init_result

        try:
            updated_at = datetime.now(timezone.utc).isoformat()
            with closing(sqlite3.connect(self.db_path)) as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "UPDATE memory_records SET value = ?, updated_at = ? WHERE key = ?",
                        (str(value), updated_at, key.strip()),
                    )
                    connection.commit()
                    if cursor.rowcount == 0:
                        return self._error("update", "Memory record not found.", details=key.strip())
                finally:
                    cursor.close()
            return self._success("update", "Memory record updated.")
        except Exception as exc:
            return self._error("update", "Failed to update memory record.", details=str(exc))

    def delete(self, key: str) -> Dict[str, Any]:
        if not isinstance(key, str) or not key.strip():
            return self._error("delete", "Memory key must be a non-empty string.")

        if not self._initialized:
            init_result = self.initialize()
            if not init_result.get("success"):
                return init_result

        try:
            with closing(sqlite3.connect(self.db_path)) as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute("DELETE FROM memory_records WHERE key = ?", (key.strip(),))
                    connection.commit()
                    if cursor.rowcount == 0:
                        return self._error("delete", "Memory record not found.", details=key.strip())
                finally:
                    cursor.close()
            return self._success("delete", "Memory record deleted.")
        except Exception as exc:
            return self._error("delete", "Failed to delete memory record.", details=str(exc))

    def list_all(self) -> Dict[str, Any]:
        if not self._initialized:
            init_result = self.initialize()
            if not init_result.get("success"):
                return init_result

        try:
            with closing(sqlite3.connect(self.db_path)) as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        "SELECT id, key, value, category, created_at, updated_at FROM memory_records ORDER BY id"
                    )
                    rows = cursor.fetchall()
                finally:
                    cursor.close()
            records = [MemoryRecord(*row).__dict__ for row in rows]
            return self._success("list_all", "Memory records listed.", result={"records": records})
        except Exception as exc:
            return self._error("list_all", "Failed to list memory records.", details=str(exc))

    def _success(self, action: str, message: str, result: Optional[Any] = None) -> Dict[str, Any]:
        response = {"success": True, "action": action, "message": message}
        if result is not None:
            response["result"] = result
        return response

    def _error(self, action: str, message: str, details: Optional[Any] = None) -> Dict[str, Any]:
        response = {"success": False, "action": action, "message": message}
        if details is not None:
            response["details"] = details
        return response
