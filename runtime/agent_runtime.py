import threading
import time
from datetime import UTC, datetime
from typing import Any, Optional

from goal_manager.goal_manager import GoalStatus


class AgentRuntime:
    """A lightweight autonomous runtime loop for EchoDesk goals."""

    def __init__(self, brain: Any, tick_interval: float = 5.0):
        self.brain = brain
        self.tick_interval = max(0.1, float(tick_interval))
        self._running = False
        self._paused = False
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.execution_history: list[dict[str, Any]] = []

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._paused = False
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False
            self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def pause(self) -> None:
        with self._lock:
            self._paused = True

    def resume(self) -> None:
        with self._lock:
            self._paused = False
            self._stop_event.set()
            self._stop_event.clear()

    def execute_goal(self, goal_id: Optional[str] = None) -> Any:
        return self.brain.run_goal(goal_id)

    def continue_goal(self, goal_id: Optional[str] = None) -> Any:
        if goal_id is None:
            next_goal = self.brain.goal_manager.get_next_goal()
            if next_goal is None:
                return {"success": False, "message": "No active goal available to continue."}
            goal_id = next_goal.id

        result = self.execute_goal(goal_id)
        status = getattr(result, "status", None)
        if status == "SUCCESS":
            self.execution_history.append({"goal_id": goal_id, "status": "completed", "result": result})
            return {"success": True, "result": result}
        self.execution_history.append({"goal_id": goal_id, "status": "failed", "result": result})
        return {"success": False, "result": result}

    def tick(self) -> None:
        with self._lock:
            if not self._running or self._paused:
                return

        if hasattr(self.brain, "scheduler") and self.brain.scheduler is not None:
            try:
                self.brain.scheduler.activate_due_goals(self.brain.goal_manager)
            except Exception:
                pass

        next_goal = self.brain.goal_manager.get_next_goal()
        if next_goal is None:
            return

        result = self.execute_goal(next_goal.id)
        self.execution_history.append(
            {
                "goal_id": next_goal.id,
                "status": getattr(result, "status", None) or "UNKNOWN",
                "result": getattr(result, "final_response", str(result)),
                "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            }
        )

    def _run_loop(self) -> None:
        while True:
            with self._lock:
                if not self._running:
                    break
                if not self._paused:
                    try:
                        self.tick()
                    except Exception:
                        pass
            self._stop_event.wait(self.tick_interval)
