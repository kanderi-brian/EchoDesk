from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from goal_manager.goal_manager import GoalManager, GoalStatus


@dataclass
class ScheduleEntry:
    id: str
    goal_id: str
    run_at: str
    recurrence: str = "once"
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_run: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScheduleEntry":
        return cls(
            id=data["id"],
            goal_id=data["goal_id"],
            run_at=data["run_at"],
            recurrence=data.get("recurrence", "once"),
            enabled=data.get("enabled", True),
            metadata=data.get("metadata", {}),
            last_run=data.get("last_run"),
        )


class Scheduler:
    DEFAULT_SCHEDULE_FILE = Path(__file__).resolve().parent / "schedule.json"

    def __init__(self, schedule_file: Optional[Path] = None):
        self.schedule_file = Path(schedule_file) if schedule_file is not None else self.DEFAULT_SCHEDULE_FILE
        self.entries: Dict[str, ScheduleEntry] = {}
        self._load_schedule()

    def _load_schedule(self) -> None:
        try:
            if self.schedule_file.exists():
                with open(self.schedule_file, "r", encoding="utf-8") as handle:
                    stored = json.load(handle)
                    self.entries = {
                        entry_data["id"]: ScheduleEntry.from_dict(entry_data)
                        for entry_data in stored
                    }
            else:
                self.entries = {}
        except (IOError, ValueError):
            self.entries = {}

    def _save_schedule(self) -> None:
        self.schedule_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.schedule_file, "w", encoding="utf-8") as handle:
            json.dump([entry.to_dict() for entry in self.entries.values()], handle, indent=2)

    def _timestamp(self, dt: Optional[datetime] = None) -> str:
        return self._as_utc(dt or datetime.now(UTC)).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    def _parse_datetime(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return self._as_utc(parsed)
        raise ValueError("run_at must be a datetime or ISO timestamp string")

    def schedule_goal(
        self,
        goal_id: str,
        run_at: Any,
        recurrence: str = "once",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ScheduleEntry:
        run_time = self._parse_datetime(run_at)
        entry = ScheduleEntry(
            id=str(uuid.uuid4()),
            goal_id=goal_id,
            run_at=self._timestamp(run_time),
            recurrence=recurrence,
            metadata=metadata or {},
        )
        self.entries[entry.id] = entry
        self._save_schedule()
        return entry

    def cancel_schedule(self, entry_id: str) -> bool:
        if entry_id in self.entries:
            del self.entries[entry_id]
            self._save_schedule()
            return True
        return False

    def get_due_entries(self, now: Optional[datetime] = None) -> List[ScheduleEntry]:
        now = self._as_utc(now or datetime.now(UTC))
        due = []
        for entry in self.entries.values():
            if not entry.enabled:
                continue
            run_at = self._parse_datetime(entry.run_at)
            if run_at <= now:
                due.append(entry)
        return due

    def _next_run(self, entry: ScheduleEntry) -> Optional[str]:
        run_at = self._parse_datetime(entry.run_at)
        if entry.recurrence == "daily":
            return self._timestamp(run_at + timedelta(days=1))
        if entry.recurrence == "weekly":
            return self._timestamp(run_at + timedelta(weeks=1))
        if entry.recurrence == "once":
            return None
        return None

    def activate_due_goals(self, goal_manager: GoalManager) -> List[ScheduleEntry]:
        due_entries = self.get_due_entries()
        activated = []
        for entry in due_entries:
            goal = goal_manager.get_goal(entry.goal_id)
            if goal is None:
                entry.enabled = False
                continue

            if goal.status in (GoalStatus.Pending, GoalStatus.Paused, GoalStatus.Failed):
                goal.status = GoalStatus.Pending
                goal.updated_at = self._timestamp()
                goal_manager.save()
                activated.append(entry)

            entry.last_run = self._timestamp()
            next_run = self._next_run(entry)
            if next_run is None:
                entry.enabled = False
            else:
                entry.run_at = next_run

        if activated:
            self._save_schedule()
        return activated

    def get_schedules(self) -> List[ScheduleEntry]:
        return list(self.entries.values())
