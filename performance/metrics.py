"""Thread-safe, dependency-free runtime metrics and expiring cache helpers."""
from __future__ import annotations

from collections import OrderedDict, defaultdict
import os
import threading
import time
from typing import Any


class TTLCache:
    """Small bounded cache with monotonic-time expiry and hit/miss accounting."""
    def __init__(self, ttl: float = 60.0, maxsize: int = 128, name: str = "cache") -> None:
        self.ttl, self.maxsize, self.name = max(0.0, ttl), max(1, maxsize), name
        self._items: OrderedDict[Any, tuple[float, Any]] = OrderedDict()
        self._lock = threading.RLock()
        self.hits = self.misses = self.evictions = 0

    def get(self, key: Any, default: Any = None) -> Any:
        with self._lock:
            item = self._items.get(key)
            if item is None or item[0] <= time.monotonic():
                if item is not None: self._items.pop(key, None)
                self.misses += 1
                return default
            self._items.move_to_end(key); self.hits += 1
            return item[1]

    def set(self, key: Any, value: Any) -> Any:
        with self._lock:
            self._items[key] = (time.monotonic() + self.ttl, value)
            self._items.move_to_end(key)
            while len(self._items) > self.maxsize:
                self._items.popitem(last=False); self.evictions += 1
        return value

    def clear(self) -> None:
        with self._lock: self._items.clear()

    def stats(self) -> dict[str, int | str]:
        with self._lock:
            return {"name": self.name, "size": len(self._items), "maxsize": self.maxsize,
                    "hits": self.hits, "misses": self.misses, "evictions": self.evictions}


class MetricsCollector:
    """Collects aggregate timings without retaining requests or sensitive payloads."""
    def __init__(self) -> None:
        self._timings: dict[str, list[float]] = defaultdict(list)
        self._counters: dict[str, int] = defaultdict(int)
        self._caches: dict[str, TTLCache] = {}
        self._lock = threading.RLock()

    def register_cache(self, cache: TTLCache) -> TTLCache:
        self._caches[cache.name] = cache; return cache

    def record(self, name: str, seconds: float) -> None:
        with self._lock:
            values = self._timings[name]; values.append(max(0.0, seconds))
            if len(values) > 500: del values[:-500]

    def increment(self, name: str, count: int = 1) -> None:
        with self._lock: self._counters[name] += count

    def summary(self) -> dict[str, Any]:
        with self._lock:
            timings = {key: {"count": len(values), "average_ms": round(sum(values) / len(values) * 1000, 3), "last_ms": round(values[-1] * 1000, 3)} for key, values in self._timings.items() if values}
            try:
                import resource
                memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
            except Exception:
                memory = 0
            return {"timings": timings, "counters": dict(self._counters), "caches": {name: cache.stats() for name, cache in self._caches.items()}, "memory_bytes": memory, "cpu_process_seconds": round(time.process_time(), 6), "pid": os.getpid()}
