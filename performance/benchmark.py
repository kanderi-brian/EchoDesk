from __future__ import annotations
import time
from typing import Any, Callable
from .metrics import MetricsCollector


class BenchmarkRunner:
    """Repeatable in-process benchmarks; callers supply safe workload functions."""
    def __init__(self, metrics: MetricsCollector | None = None) -> None:
        self.metrics = metrics or MetricsCollector()

    def run(self, name: str, workload: Callable[[], Any], iterations: int = 3) -> dict[str, Any]:
        samples = []
        for _ in range(max(1, iterations)):
            start = time.perf_counter(); workload(); samples.append(time.perf_counter() - start)
        for sample in samples: self.metrics.record("benchmark." + name, sample)
        return {"name": name, "iterations": len(samples), "min_ms": round(min(samples) * 1000, 3), "average_ms": round(sum(samples) / len(samples) * 1000, 3), "max_ms": round(max(samples) * 1000, 3)}
