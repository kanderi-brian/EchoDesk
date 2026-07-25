"""Structured, redacted audit trail for security-sensitive events."""
from __future__ import annotations
import logging
import os
from datetime import datetime, timezone
from typing import Any


class AuditLogger:
    def __init__(self, path: str = "logs/security.log", limit: int = 500) -> None:
        self.events: list[dict[str, Any]] = []
        self.limit = max(1, limit)
        self.logger = logging.getLogger("echodesk.security")
        if not self.logger.handlers:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            handler = logging.FileHandler(path, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def log(self, event: str, component: str = "security", **details: Any) -> dict[str, Any]:
        record = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event, "component": component, **self._redact(details)}
        self.events.append(record); self.events = self.events[-self.limit:]
        self.logger.info("event=%s component=%s details=%s", event, component, {key: value for key, value in record.items() if key not in {"timestamp", "event", "component"}})
        return dict(record)

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        return [dict(item) for item in self.events[-max(0, limit):]]

    @staticmethod
    def _redact(data: dict[str, Any]) -> dict[str, Any]:
        return {key: "[REDACTED]" if any(word in key.casefold() for word in ("secret", "token", "password", "credential", "key")) else value for key, value in data.items()}
