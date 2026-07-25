import time
import unittest

from performance import BenchmarkRunner, MetricsCollector, PerformanceProfiler, TTLCache
from planner.planner import PlannerEngine


class Phase21PerformanceTests(unittest.TestCase):
    def test_cache_returns_value_and_records_hit(self):
        cache = TTLCache(ttl=1, maxsize=2, name="test")
        cache.set("key", "value")
        self.assertEqual("value", cache.get("key"))
        self.assertEqual(1, cache.stats()["hits"])

    def test_cache_expires(self):
        cache = TTLCache(ttl=0.001, name="expiry")
        cache.set("key", "value"); time.sleep(0.01)
        self.assertIsNone(cache.get("key"))
        self.assertEqual(1, cache.stats()["misses"])

    def test_cache_is_bounded(self):
        cache = TTLCache(maxsize=1, name="bounded")
        cache.set("old", 1); cache.set("new", 2)
        self.assertIsNone(cache.get("old"))
        self.assertEqual(1, cache.stats()["evictions"])

    def test_metrics_exposes_cache_statistics(self):
        metrics = MetricsCollector(); metrics.register_cache(TTLCache(name="registered"))
        self.assertIn("registered", metrics.summary()["caches"])

    def test_profiler_records_elapsed_time(self):
        profiler = PerformanceProfiler()
        with profiler.measure("test_work"): pass
        self.assertEqual(1, profiler.metrics.summary()["timings"]["test_work"]["count"])

    def test_benchmark_returns_comparable_metrics(self):
        report = BenchmarkRunner().run("noop", lambda: None, iterations=2)
        self.assertEqual(2, report["iterations"])
        self.assertLessEqual(report["min_ms"], report["max_ms"])

    def test_planner_reuses_template_without_shared_mutation(self):
        planner = PlannerEngine()
        first = planner.plan("open calculator")
        first.steps[0].status = "completed"
        second = planner.plan("open calculator")
        self.assertEqual("pending", second.steps[0].status)
        self.assertGreaterEqual(planner._plan_cache.stats()["hits"], 1)

    def test_empty_plan_is_not_cached(self):
        planner = PlannerEngine()
        self.assertIsNone(planner.plan(""))
        self.assertEqual(0, planner._plan_cache.stats()["size"])


if __name__ == "__main__":
    unittest.main()
