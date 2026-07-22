from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class MemoryRecord:
    id: Optional[int]
    key: str
    value: str
    category: str
    created_at: str
    updated_at: str

    @classmethod
    def create(cls, key: str, value: str, category: str = "general") -> "MemoryRecord":
        timestamp = datetime.now(timezone.utc).isoformat()
        return cls(
            id=None,
            key=key,
            value=value,
            category=category,
            created_at=timestamp,
            updated_at=timestamp,
        )
