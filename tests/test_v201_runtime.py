import time
import unittest
from unittest.mock import patch

from executor.task_executor import TaskExecutor
from internet.internet import InternetEngine, SearchResult
from knowledge.knowledge import KnowledgeEngine
from planner.planner import Task
import main


class _SlowLLM:
    def ask(self, command, context=None): time.sleep(.04); return "completed response"

class _FakeLLM:
    def __init__(self): self.calls = 0
    def ask(self, question, context=None): self.calls += 1; return "fallback explanation"

class _FlakyProvider:
    def __init__(self): self.calls = 0
    def search(self, query, timeout):
        self.calls += 1
        return SearchResult(self.calls > 1, summary="useful result" if self.calls > 1 else None, error="HTTP 202 pending")


class V201RuntimeTests(unittest.TestCase):
    def test_llm_waits_past_generic_timeout(self):
        executor = TaskExecutor(llm_engine=_SlowLLM(), task_timeout=.001, llm_timeout=0, record_learning=False)
        result = executor._execute_task_with_retry(Task("1", "ask", "LLM"), "hello")
        self.assertTrue(result["success"]); self.assertIn("completed", result["message"])

    def test_llm_configured_timeout_returns_failure_once(self):
        executor = TaskExecutor(llm_engine=_SlowLLM(), llm_timeout=.001, retry_limit=0, record_learning=False)
        result = executor._execute_task_with_retry(Task("1", "ask", "LLM"), "hello")
        self.assertFalse(result["success"]); self.assertIn("timed out", result["message"])

    def test_llm_records_runtime_breakdown(self):
        executor = TaskExecutor(llm_engine=_FakeLLM(), record_learning=False)
        executor._execute_llm("hello")
        self.assertIn("inference_time", executor.last_llm_timings)
        self.assertIn("total_response_time", executor.last_llm_timings)

    def test_knowledge_uses_llm_when_local_lookup_misses(self):
        llm = _FakeLLM(); engine = KnowledgeEngine(llm_engine=llm)
        self.assertEqual("fallback explanation", engine.search("Explain closures in programming"))
        self.assertEqual(1, llm.calls)

    def test_knowledge_caches_successful_fallback(self):
        llm = _FakeLLM(); engine = KnowledgeEngine(llm_engine=llm)
        engine.search("Explain closures in programming"); engine.search("Explain closures in programming")
        self.assertEqual(1, llm.calls)

    def test_local_knowledge_precedes_llm(self):
        llm = _FakeLLM(); engine = KnowledgeEngine(llm_engine=llm)
        self.assertIn("objects", engine.search("Explain object-oriented programming")); self.assertEqual(0, llm.calls)

    def test_internet_retries_transient_result(self):
        provider = _FlakyProvider(); engine = InternetEngine(providers=[provider], retries=1)
        self.assertIn("useful", engine.search("test")); self.assertEqual(2, provider.calls)

    def test_internet_failure_has_actionable_error(self):
        engine = InternetEngine(providers=[_FlakyProvider()], retries=0)
        self.assertIn("HTTP 202", engine.search("test"))

    def test_console_flag_skips_studio(self):
        with patch.object(main, "studio_available", return_value=True), patch.object(main, "console_main") as console:
            main.main(["--console"])
        console.assert_called_once()

    def test_startup_diagnostics_describes_studio(self):
        with patch.object(main, "studio_available", return_value=False):
            self.assertIn("PySide6", main.startup_diagnostics()["studio"])


if __name__ == "__main__": unittest.main()
