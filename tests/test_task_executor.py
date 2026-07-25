import unittest

from executor.task_executor import TaskExecutor, ExecutionStatus, Task
from planner.planner import ExecutionPlan, PlanStep


class DummyExecutor(TaskExecutor):
    def __init__(self):
        super().__init__()
        self.call_count = 0

    def _execute_memory(self, command: str) -> str:
        self.call_count += 1
        if self.call_count == 1:
            raise RuntimeError("Temporary failure")
        return "memory result"

    def _execute_knowledge(self, command: str) -> str:
        return "knowledge result"

    def _execute_internet(self, command: str) -> str:
        return "internet result"

    def _execute_llm(self, command: str) -> str:
        return "llm result"


class TestTaskExecutor(unittest.TestCase):
    def test_sequential_tasks_execute_and_report_progress(self):
        plan = ExecutionPlan(
            goal="Search today's AI news and summarize it",
            steps=[
                PlanStep(id="1", tool="internet", action="Search internet", description="Search today's AI news.", expected_result="Find AI news."),
                PlanStep(id="2", tool="llm", action="Summarize results", description="Summarize search results.", expected_result="Provide a summary."),
            ],
        )
        plan.tasks = [
            Task(id="t1", description="Search today's AI news.", capability="Internet"),
            Task(id="t2", description="Summarize search results.", capability="LLM"),
        ]

        executor = DummyExecutor()
        result = executor.execute_plan(plan, plan.goal)

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(len(result.tasks), 2)
        self.assertEqual(result.tasks[0].status, ExecutionStatus.SUCCESS)
        self.assertEqual(result.tasks[1].status, ExecutionStatus.SUCCESS)
        self.assertIn("[Internet]", result.final_response)
        self.assertIn("[LLM]", result.final_response)

    def test_retry_logic_retries_once_on_failure(self):
        plan = ExecutionPlan(
            goal="Remember my favorite language is Python.",
            steps=[
                PlanStep(id="1", tool="memory", action="Manage memory", description="Remember favorite language.", expected_result="Store favorite language."),
            ],
        )
        plan.tasks = [Task(id="t1", description="Remember favorite language.", capability="Memory")]

        executor = DummyExecutor()
        result = executor.execute_plan(plan, plan.goal)

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.tasks[0].status, ExecutionStatus.SUCCESS)
        self.assertEqual(executor.call_count, 2)

    def test_failed_task_blocks_dependent_summary(self):
        plan = ExecutionPlan(
            goal="Search today's AI news and summarize it",
            steps=[
                PlanStep(id="1", tool="internet", action="Search internet", description="Search today's AI news.", expected_result="Find AI news."),
                PlanStep(id="2", tool="llm", action="Summarize results", description="Summarize search results.", expected_result="Provide a summary."),
            ],
        )
        plan.tasks = [
            Task(id="t1", description="Search today's AI news.", capability="Internet"),
            Task(id="t2", description="Summarize search results.", capability="LLM"),
        ]

        class FailingExecutor(TaskExecutor):
            def _execute_internet(self, command: str) -> str:
                raise RuntimeError("Internet unavailable")

        executor = FailingExecutor()
        result = executor.execute_plan(plan, plan.goal)

        self.assertEqual(result.status, "FAILED")
        self.assertEqual(result.tasks[0].status, ExecutionStatus.FAILED)
        self.assertEqual(result.tasks[1].status, ExecutionStatus.PENDING)


if __name__ == "__main__":
    unittest.main()
