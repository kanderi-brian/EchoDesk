import threading
import time
import unittest
from types import SimpleNamespace

from execution.engine import ExecutionEngine
from execution.result import ExecutionResult
from planner.planner import ExecutionPlan, PlanStep


class DummyStepExecutor:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def execute_step(self, step):
        self.calls.append(step)
        if not self.responses:
            return {"success": False, "message": "No response configured."}
        return self.responses.pop(0)


class FailingOnceExecutor:
    def __init__(self):
        self.call_count = 0

    def execute_step(self, step):
        self.call_count += 1
        if self.call_count == 1:
            return {"success": False, "message": "Temporary failure."}
        return {"success": True, "message": "Recovered."}


class SlowExecutor:
    def __init__(self, delay=0.3):
        self.delay = delay
        self.calls = 0

    def execute_step(self, step):
        self.calls += 1
        time.sleep(self.delay)
        return {"success": True, "message": f"Step {self.calls} completed."}


class TestExecutionEngine(unittest.TestCase):
    def make_plan(self, step_count, optional_flags=None):
        steps = []
        optional_flags = optional_flags or [False] * step_count
        for idx in range(step_count):
            steps.append(
                PlanStep(
                    id=f"step{idx}",
                    tool="test",
                    action=f"Action {idx}",
                    description=f"Description {idx}",
                    expected_result=f"Expected {idx}",
                    optional=optional_flags[idx],
                )
            )
        return ExecutionPlan(goal="test plan", steps=steps)

    def test_execute_plan_sequentially(self):
        plan = self.make_plan(2)
        executor = ExecutionEngine(step_executor=DummyStepExecutor([
            {"success": True, "message": "ok1"},
            {"success": True, "message": "ok2"},
        ]))

        result = executor.execute_plan(plan)
        self.assertTrue(result.success)
        self.assertEqual(result.completed_steps, 2)
        self.assertIsNone(result.failed_step)
        self.assertIn("Step succeeded", " ".join(result.logs))
        self.assertEqual(result.output, "Execution completed successfully.")
        self.assertGreaterEqual(result.execution_time, 0.0)

    def test_execute_plan_optional_step_continues_on_failure(self):
        plan = self.make_plan(3, optional_flags=[False, True, False])
        executor = ExecutionEngine(step_executor=DummyStepExecutor([
            {"success": True, "message": "ok1"},
            {"success": False, "message": "optional fail"},
            {"success": True, "message": "ok3"},
        ]))

        result = executor.execute_plan(plan, max_retries=0)
        self.assertTrue(result.success)
        self.assertEqual(result.completed_steps, 2)
        self.assertIsNone(result.failed_step)
        self.assertIn("Optional step failed; continuing execution", " ".join(result.logs))

    def test_execute_plan_stops_on_required_failure(self):
        plan = self.make_plan(2)
        executor = ExecutionEngine(step_executor=DummyStepExecutor([
            {"success": True, "message": "ok1"},
            {"success": False, "message": "required fail"},
        ]))

        result = executor.execute_plan(plan, max_retries=0)
        self.assertFalse(result.success)
        self.assertEqual(result.completed_steps, 1)
        self.assertEqual(result.failed_step, plan.steps[1])
        self.assertEqual(result.error, "required fail")

    def test_retry_step_succeeds_after_one_failure(self):
        plan = self.make_plan(1)
        executor = ExecutionEngine(step_executor=FailingOnceExecutor())

        result = executor.execute_plan(plan, max_retries=1)
        self.assertTrue(result.success)
        self.assertEqual(result.completed_steps, 1)
        self.assertEqual(executor.step_executor.call_count, 2)
        self.assertEqual(result.retry_attempts, 1)
        self.assertIn("recovered", " ".join(result.recovered_failures).lower())

    def test_skip_current_step_continues_execution(self):
        plan = self.make_plan(2)
        plan.steps[0].status = "failed"
        executor = ExecutionEngine(step_executor=DummyStepExecutor([
            {"success": True, "message": "ok2"},
        ]))

        executor.current_plan = plan
        skip_result = executor.skip_current_step()

        self.assertTrue(skip_result["success"])
        self.assertEqual(plan.steps[0].status, "skipped")

    def test_execution_summary_includes_step_counts(self):
        plan = self.make_plan(2, optional_flags=[False, True])
        executor = ExecutionEngine(step_executor=DummyStepExecutor([
            {"success": True, "message": "ok1"},
            {"success": False, "message": "optional fail"},
        ]))

        result = executor.execute_plan(plan, max_retries=0)
        self.assertTrue(result.success)
        self.assertIn("Completed steps: 1", result.output)
        self.assertIn("Skipped steps: 1", result.output)
        self.assertIn("Failed steps: 0", result.output)
        executor = ExecutionEngine(step_executor=DummyStepExecutor([]))
        self.assertFalse(executor.is_paused)
        executor.pause_execution()
        self.assertTrue(executor.is_paused)
        executor.resume_execution()
        self.assertFalse(executor.is_paused)

    def test_cancel_execution_stops_plan(self):
        plan = self.make_plan(2)
        slow_executor = SlowExecutor(delay=0.1)
        executor = ExecutionEngine(step_executor=slow_executor)
        result_holder = {}

        def run_plan():
            result_holder["result"] = executor.execute_plan(plan)

        thread = threading.Thread(target=run_plan)
        thread.start()
        time.sleep(0.05)
        executor.cancel_execution()
        thread.join(timeout=1.0)

        self.assertIn("result", result_holder)
        self.assertFalse(result_holder["result"].success)
        self.assertEqual(result_holder["result"].error, "Execution cancelled.")

    def test_execute_plan_invalid_plan_returns_error(self):
        executor = ExecutionEngine(step_executor=DummyStepExecutor([]))
        result = executor.execute_plan("not a plan")

        self.assertFalse(result.success)
        self.assertEqual(result.error, "Invalid execution plan.")
        self.assertIn("Invalid execution plan provided.", result.logs)


if __name__ == "__main__":
    unittest.main()
