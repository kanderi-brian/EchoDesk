from __future__ import annotations
from contextlib import contextmanager
import logging
import os
import time
from .metrics import MetricsCollector


class PerformanceProfiler:
    """Records timings to a collector and the dedicated performance log."""
    def __init__(self, metrics: MetricsCollector | None = None) -> None:
        self.metrics = metrics or MetricsCollector()
        self.logger = logging.getLogger("echodesk.performance")
        if not self.logger.handlers:
            os.makedirs("logs", exist_ok=True)
            handler = logging.FileHandler(os.path.join("logs", "performance.log"), encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            self.logger.addHandler(handler); self.logger.setLevel(logging.INFO)

    @contextmanager
    def measure(self, name: str):
        start = time.perf_counter()
        try: yield
        finally:
            elapsed = time.perf_counter() - start
            self.metrics.record(name, elapsed)
            self.logger.info("metric=%s elapsed_ms=%.3f", name, elapsed * 1000)
