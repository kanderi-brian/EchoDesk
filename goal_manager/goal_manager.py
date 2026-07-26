import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.app_paths import data_root


DEFAULT_GOAL_FILE = data_root() / "goals.json"


class GoalStatus:
    Pending = "Pending"
    Planning = "Planning"
    Running = "Running"
    Paused = "Paused"
    Completed = "Completed"
    Failed = "Failed"
    Cancelled = "Cancelled"


@dataclass
class Goal:
    id: str
    title: str
    description: str
    priority: int = 50
    status: str = GoalStatus.Pending
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    dependencies: List[str] = field(default_factory=list)
    progress: float = 0.0
    current_step: Optional[str] = None
    completed_steps: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "dependencies": list(self.dependencies),
            "progress": self.progress,
            "current_step": self.current_step,
            "completed_steps": list(self.completed_steps),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Goal":
        return cls(
            id=str(data.get("id", str(uuid.uuid4()))),
            title=str(data.get("title", "")),
            description=str(data.get("description", "")),
            priority=int(data.get("priority", 50)),
            status=str(data.get("status", GoalStatus.Pending)),
            created_at=str(data.get("created_at", datetime.now().isoformat())),
            updated_at=str(data.get("updated_at", datetime.now().isoformat())),
            dependencies=list(data.get("dependencies", [])),
            progress=float(data.get("progress", 0.0)),
            current_step=data.get("current_step"),
            completed_steps=list(data.get("completed_steps", [])),
            metadata=dict(data.get("metadata", {})),
        )


class GoalManager:
    """Manage long-running goals for EchoDesk."""

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path) if storage_path else DEFAULT_GOAL_FILE
        self.goals: Dict[str, Goal] = {}
        self.load()

    def create_goal(
        self,
        title: str,
        description: Optional[str] = None,
        priority: int = 50,
        dependencies: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Goal:
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Goal title must be a non-empty string.")

        description_text = description.strip() if isinstance(description, str) and description.strip() else title.strip()
        goal = Goal(
            id=str(uuid.uuid4()),
            title=title.strip(),
            description=description_text,
            priority=max(0, int(priority)),
            status=GoalStatus.Pending,
            dependencies=list(dependencies or []),
            metadata=dict(metadata or {}),
        )
        self.goals[goal.id] = goal
        self.save()
        return goal

    def remove_goal(self, goal_id: str) -> bool:
        if goal_id in self.goals:
            del self.goals[goal_id]
            self.save()
            return True
        return False

    def pause_goal(self, goal_id: str) -> bool:
        goal = self.get_goal(goal_id)
        if goal is None or goal.status in (GoalStatus.Completed, GoalStatus.Cancelled):
            return False
        goal.status = GoalStatus.Paused
        goal.updated_at = datetime.now().isoformat()
        self.save()
        return True

    def resume_goal(self, goal_id: str) -> bool:
        goal = self.get_goal(goal_id)
        if goal is None or goal.status == GoalStatus.Completed or goal.status == GoalStatus.Cancelled:
            return False
        goal.status = GoalStatus.Running
        goal.updated_at = datetime.now().isoformat()
        self.save()
        return True

    def cancel_goal(self, goal_id: str) -> bool:
        goal = self.get_goal(goal_id)
        if goal is None or goal.status == GoalStatus.Completed:
            return False
        goal.status = GoalStatus.Cancelled
        goal.updated_at = datetime.now().isoformat()
        self.save()
        return True

    def complete_goal(self, goal_id: str) -> bool:
        goal = self.get_goal(goal_id)
        if goal is None:
            return False
        goal.status = GoalStatus.Completed
        goal.progress = 100.0
        goal.updated_at = datetime.now().isoformat()
        if goal.current_step:
            goal.completed_steps.append(goal.current_step)
            goal.current_step = None
        self.save()
        return True

    def update_progress(
        self,
        goal_id: str,
        progress: float,
        current_step: Optional[str] = None,
        completed_steps: Optional[List[str]] = None,
    ) -> bool:
        goal = self.get_goal(goal_id)
        if goal is None:
            return False
        goal.progress = max(0.0, min(100.0, float(progress)))
        if current_step is not None:
            goal.current_step = current_step
        if completed_steps is not None:
            goal.completed_steps = list(completed_steps)
        goal.updated_at = datetime.now().isoformat()
        self.save()
        return True

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        return self.goals.get(goal_id)

    def find_goal(self, identifier: str) -> Optional[Goal]:
        if not isinstance(identifier, str) or not identifier.strip():
            return None
        identifier_text = identifier.strip().lower()
        if identifier in self.goals:
            return self.goals[identifier]
        for goal in self.goals.values():
            if goal.title.lower() == identifier_text or goal.description.lower() == identifier_text:
                return goal
        return None

    def get_all_goals(self) -> List[Goal]:
        return sorted(self.goals.values(), key=lambda item: (item.priority, item.created_at))

    def get_active_goals(self) -> List[Goal]:
        return [
            goal
            for goal in self.get_all_goals()
            if goal.status in (GoalStatus.Pending, GoalStatus.Planning, GoalStatus.Running)
        ]

    def get_unfinished_goals(self) -> List[Goal]:
        return [
            goal
            for goal in self.get_all_goals()
            if goal.status in (GoalStatus.Pending, GoalStatus.Planning, GoalStatus.Running, GoalStatus.Paused, GoalStatus.Failed)
        ]

    def resume_interrupted_goals(self) -> int:
        resumed = 0
        for goal in self.goals.values():
            if goal.status == GoalStatus.Running:
                goal.status = GoalStatus.Pending
                goal.updated_at = datetime.now().isoformat()
                resumed += 1
        if resumed:
            self.save()
        return resumed

    def get_next_goal(self) -> Optional[Goal]:
        available_goals = [
            goal
            for goal in self.get_active_goals()
            if self._dependencies_complete(goal)
        ]
        if not available_goals:
            return None
        return sorted(available_goals, key=lambda item: (item.priority, item.created_at))[0]

    def get_goals_by_status(self, status: str) -> List[Goal]:
        return [goal for goal in self.get_all_goals() if goal.status == status]

    def save(self) -> bool:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as file:
                json.dump([goal.to_dict() for goal in self.goals.values()], file, indent=2)
            return True
        except Exception:
            return False

    def load(self) -> List[Goal]:
        self.goals.clear()
        if not self.storage_path.exists():
            return []
        try:
            with open(self.storage_path, "r", encoding="utf-8") as file:
                data = json.load(file)
            for item in data:
                goal = Goal.from_dict(item)
                self.goals[goal.id] = goal
        except Exception:
            self.goals.clear()
        return list(self.goals.values())

    def _dependencies_complete(self, goal: Goal) -> bool:
        for dependency_id in goal.dependencies:
            dependency = self.get_goal(dependency_id)
            if dependency is None or dependency.status != GoalStatus.Completed:
                return False
        return True
