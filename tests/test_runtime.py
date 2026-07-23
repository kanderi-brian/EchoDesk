import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from runtime.runtime import RuntimeEngine
from planner.planner import ExecutionPlan, PlanStep


class DummyExecutionEngine:
    def execute_plan(self, plan):
        return SimpleNamespace(success=True, output="executed")


class FailingExecutionEngine:
    def execute_plan(self, plan):
        raise RuntimeError("Failure during execution")


class TestRuntimeEngine(unittest.TestCase):
    def test_execute_route_executes_plan_with_execution_engine(self):
        runtime = RuntimeEngine()
        runtime.tool_manager.register_tool("ExecutionEngine", DummyExecutionEngine())

        plan = ExecutionPlan(
            goal="test",
            steps=[
                PlanStep(
                    id="1",
                    tool="test",
                    action="Action",
                    description="Description",
                    expected_result="Expected",
                )
            ],
        )
        route_payload = {"route": "execute_plan", "plan": plan}
        response = runtime._execute_route("test", route_payload)

        self.assertEqual(response, "executed")

    def test_execute_route_returns_missing_engine_message(self):
        runtime = RuntimeEngine()
        runtime.tool_manager.unregister_tool("ExecutionEngine")
        route_payload = {"route": "execute_plan", "plan": {}}

        self.assertEqual(runtime._execute_route("test", route_payload), "Execution engine is not available.")

    def test_execute_route_returns_no_plan_message(self):
        runtime = RuntimeEngine()
        runtime.tool_manager.register_tool("ExecutionEngine", DummyExecutionEngine())

        response = runtime._execute_route("test", {"route": "execute_plan", "plan": None})
        self.assertEqual(response, "No execution plan was provided.")

    def test_execute_route_handles_execution_exception_gracefully(self):
        runtime = RuntimeEngine()
        runtime.tool_manager.register_tool("ExecutionEngine", FailingExecutionEngine())
 
        plan = ExecutionPlan(goal="test", steps=[])
        response = runtime._execute_route("test", {"route": "execute_plan", "plan": plan})
 
        self.assertIn("Execution failed with an exception", response)
 
    def test_execute_route_resumes_pending_execution(self):
        runtime = RuntimeEngine()
        executor = mock = Mock()
        executor.is_paused = False
        current_plan = ExecutionPlan(goal="test", steps=[])
        executor.current_plan = current_plan
        executor.execute_plan.return_value = SimpleNamespace(success=True, output="resumed")
        runtime.tool_manager.register_tool("ExecutionEngine", executor)
 
        response = runtime._execute_route("continue", "resume_execution")
 
        self.assertEqual(response, "resumed")
        executor.execute_plan.assert_called_once_with(current_plan)
 
    def test_execute_route_cancels_execution(self):
        runtime = RuntimeEngine()
        executor = Mock()
        runtime.tool_manager.register_tool("ExecutionEngine", executor)
 
        response = runtime._execute_route("cancel", "cancel_execution")
 
        self.assertEqual(response, "Execution cancelled.")
        executor.cancel_execution.assert_called_once()
 
    def test_execute_route_retries_failed_step(self):
        runtime = RuntimeEngine()
        executor = Mock()
        executor.retry_step.return_value = {"success": True, "message": "Retried"}
        executor.current_plan = ExecutionPlan(goal="test", steps=[])
        executor.execute_plan.return_value = SimpleNamespace(success=True, output="continued")
        runtime.tool_manager.register_tool("ExecutionEngine", executor)
 
        response = runtime._execute_route("retry the failed step", "retry_step")
 
        self.assertEqual(response, "continued")
        executor.retry_step.assert_called_once()
 
    def test_execute_route_skips_current_step(self):
        runtime = RuntimeEngine()
        executor = Mock()
        executor.skip_current_step.return_value = {"success": True, "message": "Skipped step"}
        executor.current_plan = ExecutionPlan(goal="test", steps=[])
        executor.execute_plan.return_value = SimpleNamespace(success=True, output="continued")
        runtime.tool_manager.register_tool("ExecutionEngine", executor)
 
        response = runtime._execute_route("skip this step", "skip_step")
 
        self.assertEqual(response, "continued")
        executor.skip_current_step.assert_called_once()
 
    def test_execute_route_uses_llm_for_unknown_route(self):
        runtime = RuntimeEngine()
        llm_engine = Mock()
        llm_engine.ask.return_value = "LLM fallback response."
        runtime.tool_manager.register_tool("LLMEngine", llm_engine)

        response = runtime._execute_route("Tell me a story.", "unknown")

        self.assertEqual(response, "LLM fallback response.")

    def test_execute_route_uses_llm_for_greeting_route(self):
        runtime = RuntimeEngine()
        runtime.context_engine.clear()
        llm_engine = Mock()
        llm_engine.ask.return_value = "LLM greeting response."
        runtime.tool_manager.register_tool("LLMEngine", llm_engine)

        response = runtime._execute_route("hello", "greeting")

        self.assertEqual(response, "LLM greeting response.")
        llm_engine.ask.assert_called_once()
        self.assertEqual(llm_engine.ask.call_args[0][0], "hello")

    def test_execute_route_falls_back_to_llm_when_knowledge_and_internet_unavailable(self):
        runtime = RuntimeEngine()
        runtime.knowledge_engine = Mock(search=Mock(return_value=None))
        runtime.internet_engine = None
        llm_engine = Mock()
        llm_engine.ask.return_value = "LLM fallback response."
        runtime.tool_manager.register_tool("LLMEngine", llm_engine)

        response = runtime._execute_route("What is recursion?", "knowledge")

        self.assertEqual(response, "LLM fallback response.")
 
 
if __name__ == "__main__":
    unittest.main()
