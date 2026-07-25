"""Safe, metadata-only strategy learning for EchoDesk."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import logging
import os
from typing import Any


@dataclass
class StrategyRecord:
    name: str
    workflow: str = ""
    success_count: int = 0
    failure_count: int = 0
    usage_frequency: int = 0
    average_execution_time: float = 0.0
    average_confidence: float = 0.0
    verification_success_rate: float = 0.0
    last_used: str = ""
    last_failure: str = ""

    @property
    def score(self) -> float:
        attempts = self.success_count + self.failure_count
        success_rate = self.success_count / attempts if attempts else 0.0
        speed = 1 / (1 + self.average_execution_time)
        return round((success_rate * .5) + (self.verification_success_rate * .25) + (self.average_confidence * .15) + (speed * .1), 4)


class LearningEngine:
    """Records outcomes and returns explainable planning recommendations only."""
    def __init__(self, memory_engine: Any) -> None:
        self.memory_engine = memory_engine
        self._store = getattr(memory_engine, "_payload", {}).setdefault("learning", {"strategies": {}, "events": [], "workflows": {}})
        self.logger = logging.getLogger("echodesk.learning")
        if not self.logger.handlers:
            os.makedirs("logs", exist_ok=True)
            handler = logging.FileHandler(os.path.join("logs", "learning.log"), encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def record_outcome(self, strategy: str, success: bool, *, workflow: str = "", duration: float = 0.0, confidence: float = 0.0, verification_success: bool = False, complexity: float = 0.0, retries: int = 0, recovery_used: bool = False, failure: str = "", approval: bool | None = None) -> StrategyRecord:
        key = self._key(strategy)
        data = self._store["strategies"].setdefault(key, asdict(StrategyRecord(name=strategy, workflow=workflow)))
        data["usage_frequency"] += 1
        data["success_count" if success else "failure_count"] += 1
        count = data["usage_frequency"]
        data["average_execution_time"] = self._average(data["average_execution_time"], duration, count)
        data["average_confidence"] = self._average(data["average_confidence"], confidence, count)
        verified = int(data["verification_success_rate"] * (count - 1)) + int(verification_success)
        data["verification_success_rate"] = verified / count
        data["last_used"] = self._now()
        data["workflow"] = workflow or data.get("workflow", "")
        if failure: data["last_failure"] = failure
        event = {"strategy": strategy, "success": success, "duration": duration, "confidence": confidence, "verification": verification_success, "complexity": complexity, "retries": retries, "recovery_used": recovery_used, "approval": approval, "timestamp": self._now()}
        self._store["events"].append(event)
        self._store["events"] = self._store["events"][-200:]
        if workflow:
            self._store["workflows"].setdefault(self._key(workflow), []).append(key)
        self._persist()
        self.logger.info("strategy=%s success=%s confidence=%.2f", strategy, success, confidence)
        return self._record(data)

    record_learning_event = record_outcome

    def record_security_event(self, event: str, success: bool, *, risk: str = "low", component: str = "security") -> StrategyRecord:
        """Record security outcomes for analysis only; it never alters policy."""
        return self.record_outcome(f"security:{event}", success, workflow=f"security:{component}", confidence=0.0, failure="" if success else risk)

    def recommend_strategy(self, goal: str, limit: int = 3) -> list[StrategyRecord]:
        terms = set(self._key(goal).split())
        records = [self._record(value) for value in self._store["strategies"].values()]
        matching = [record for record in records if terms & set(self._key(record.name + " " + record.workflow).split())] or records
        ranked = sorted(matching, key=lambda record: (record.score, record.usage_frequency, record.last_used), reverse=True)[:max(0, limit)]
        self.logger.info("strategy recommendation goal=%r count=%d", goal, len(ranked))
        return ranked

    def recommend_workflow(self, goal: str, limit: int = 3) -> list[StrategyRecord]:
        return [item for item in self.recommend_strategy(goal, limit) if item.workflow]

    def recommend_recovery(self, failure: str, limit: int = 3) -> list[StrategyRecord]:
        text = self._key(failure)
        candidates = [self._record(item) for item in self._store["strategies"].values() if item.get("failure_count", 0) and (not text or text in self._key(str(item.get("last_failure", "")) + " " + str(item.get("name", ""))))]
        return sorted(candidates, key=lambda item: (item.score, item.failure_count), reverse=True)[:limit]

    def recommend_plan(self, goal: str, limit: int = 3) -> dict[str, Any]:
        strategies = self.recommend_strategy(goal, limit)
        return {"goal": goal, "strategies": strategies, "avoid": self.recommend_recovery(goal, limit), "reason": self.explain_strategy(strategies[0]) if strategies else "No prior strategy is available."}

    def explain_strategy(self, strategy: StrategyRecord | str) -> str:
        record = strategy if isinstance(strategy, StrategyRecord) else next((item for item in self.recommend_strategy(strategy, 100) if self._key(item.name) == self._key(strategy)), None)
        if record is None: return "No learning history is available for this strategy."
        return f"'{record.name}' was selected because it succeeded {record.success_count} time(s), has a {record.verification_success_rate:.0%} verification rate, and a score of {record.score:.2f}."

    def update_preference(self, category: str, key: str, value: str, confidence: float = .5) -> Any:
        result = self.memory_engine.remember_preference(category, key, value, confidence=max(0.0, min(1.0, confidence)), auto_flush=False)
        self._persist()
        self.logger.info("preference updated category=%s key=%s", category, key)
        return result

    def decay_preferences(self, amount: float = .05) -> int:
        changed = 0
        for preference in self.memory_engine.get_preferences():
            confidence = round(max(0.0, preference.confidence - max(0.0, amount)), 6)
            self.memory_engine.update_preference(preference.category, preference.key, preference.value, confidence=confidence)
            changed += 1
        if changed:
            self._persist()
        return changed

    def get_statistics(self) -> dict[str, Any]:
        records = [self._record(value) for value in self._store["strategies"].values()]
        failures = sorted((item for item in records if item.failure_count), key=lambda item: item.failure_count, reverse=True)
        return {"strategy_count": len(records), "event_count": len(self._store["events"]), "top_strategies": sorted(records, key=lambda item: item.score, reverse=True)[:5], "common_failures": failures[:5], "workflow_count": len(self._store["workflows"]), "preferences": self.memory_engine.get_preferences(), "learning_confidence": sum(item.average_confidence for item in records) / len(records) if records else 0.0}

    @staticmethod
    def _key(value: str) -> str: return " ".join(str(value).casefold().split())
    @staticmethod
    def _average(current: float, incoming: float, count: int) -> float: return ((float(current) * (count - 1)) + float(incoming)) / count
    @staticmethod
    def _now() -> str: return datetime.now(timezone.utc).isoformat()
    @staticmethod
    def _record(data: dict[str, Any]) -> StrategyRecord: return StrategyRecord(**{key: data.get(key, field.default) for key, field in StrategyRecord.__dataclass_fields__.items()})
    def _persist(self) -> None:
        if hasattr(self.memory_engine, "_mark_dirty"): self.memory_engine._mark_dirty()
        if hasattr(self.memory_engine, "flush"): self.memory_engine.flush()
