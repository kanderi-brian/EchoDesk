import unittest
from unittest.mock import Mock

from executor.task_executor import TaskExecutor


class FakeEntry:
    def __init__(self, user, assistant):
        self.user = user
        self.assistant = assistant


class TestTaskExecutorLLMContextLimiting(unittest.TestCase):
    def test_memory_context_limit_is_respected(self):
        # Create a TaskExecutor with a mock memory engine that returns many entries
        mem = Mock()
        entries = [FakeEntry(f'user{i}', f'assistant{i}') for i in range(10)]
        mem.get_recent_context.return_value = entries

        provider = Mock()
        provider.generate.return_value = "ok"

        # inject provider into LLM engine by creating a real LLMEngine
        from llm.engine import LLMEngine
        llm = LLMEngine(provider=provider)

        exec = TaskExecutor(memory_engine=mem, llm_engine=llm)
        # call _execute_llm directly
        out = exec._execute_llm("do something")
        # provider.generate was called once with prompt containing at most 5 entries
        sent_prompt = provider.generate.call_args[0][0]
        self.assertTrue(sent_prompt.count("User:") <= 5)


if __name__ == '__main__':
    unittest.main()
