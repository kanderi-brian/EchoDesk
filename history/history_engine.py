from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class HistoryEngine:
    DEFAULT_HISTORY_FILE = Path(__file__).resolve().parent / "history.json"

    def __init__(self, history_file: Optional[Path] = None):
        self.history_file = Path(history_file) if history_file is not None else self.DEFAULT_HISTORY_FILE
        self.history: List[Dict[str, Any]] = []
        self._load_history()

    def _load_history(self) -> None:
        try:
            if self.history_file.exists():
                with open(self.history_file, "r", encoding="utf-8") as handle:
                    self.history = json.load(handle)
            else:
                self.history = []
        except (IOError, ValueError):
            self.history = []

    def _save_history(self) -> None:
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_file, "w", encoding="utf-8") as handle:
            json.dump(self.history, handle, indent=2)

    def _record_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type,
            "payload": payload,
        }
        self.history.append(event)
        self._save_history()

    def record_goal_event(self, goal: Any, event_type: str, details: Optional[str] = None) -> None:
        payload = {
            "goal_id": getattr(goal, "id", None),
            "title": getattr(goal, "title", None),
            "status": getattr(goal, "status", None),
            "details": details,
        }
        self._record_event(f"goal_{event_type}", payload)

    def record_plan(self, plan: Any, status: str, result: Any, goal_id: Optional[str] = None) -> None:
        payload = {
            "goal_id": goal_id,
            "status": status,
            "result": getattr(result, "final_response", result),
            "tasks": [
                {
                    "tool": task.tool,
                    "description": task.description,
                    "capability": task.capability,
                    "status": getattr(task, "status", None),
                }
                for task in getattr(plan, "tasks", [])
            ],
        }
        self._record_event("plan_completed", payload)

    def record_reflection(self, feedback: Dict[str, Any]) -> None:
        self._record_event("reflection", feedback)

    def get_history(self, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        if event_type is None:
            return self.history
        return [event for event in self.history if event["event_type"] == event_type]

    def get_goal_history(self, goal_id: str) -> List[Dict[str, Any]]:
        return [event for event in self.history if event["payload"].get("goal_id") == goal_id]

    def get_failed_goals(self) -> List[Dict[str, Any]]:
        return [event for event in self.history if event["event_type"] == "goal_execution_failed"]

    def get_completed_goals(self) -> List[Dict[str, Any]]:
        return [event for event in self.history if event["event_type"] == "goal_execution_completed"]
