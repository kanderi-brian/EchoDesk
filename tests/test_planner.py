import unittest

from planner.planner import ExecutionPlan, PlanStep, PlannerEngine


class TestPlanner(unittest.TestCase):
    def test_plan_step_and_execution_plan(self):
        step = PlanStep(
            id="step1",
            tool="Chrome",
            action="Launch application",
            description="Launch Chrome.",
            expected_result="Chrome opens.",
        )

        self.assertEqual(step.id, "step1")
        self.assertEqual(step.tool, "Chrome")
        self.assertEqual(step.action, "Launch application")
        self.assertEqual(step.expected_result, "Chrome opens.")
        self.assertFalse(step.optional)
        self.assertIsInstance(step.to_dict(), dict)
        self.assertIn("engine", step.to_dict())
        self.assertEqual(step.to_dict()["retry_count"], 0)

        plan = ExecutionPlan(goal="Open Chrome")
        self.assertTrue(plan.is_complete())
        self.assertIsNone(plan.next_step())

        plan.add_step(step)
        self.assertFalse(plan.is_complete())
        self.assertIs(plan.next_step(), step)

        step.status = "completed"
        self.assertTrue(plan.is_complete())

    def test_single_step_plan_open_application(self):
        planner = PlannerEngine()
        plan = planner.plan("open chrome")

        self.assertIsNotNone(plan)
        self.assertIsInstance(plan, ExecutionPlan)
        self.assertEqual(plan.goal, "open chrome")
        self.assertEqual(len(plan.steps), 2)
        self.assertEqual(plan.estimated_complexity, "easy")
        self.assertIn("automation", plan.required_tools)
        self.assertFalse(plan.requires_confirmation)
        self.assertIn("Launch application", plan.steps[0].action)
        self.assertIn("Wait", plan.steps[1].action)

    def test_multi_step_plan_complexity(self):
        planner = PlannerEngine()
        plan = planner.plan("fix python importerror")

        self.assertIsNotNone(plan)
        self.assertEqual(plan.goal, "fix python importerror")
        self.assertGreaterEqual(len(plan.steps), 4)
        self.assertEqual(plan.estimated_complexity, "hard")
        self.assertTrue(plan.requires_confirmation)
        self.assertIn("Capture screen", [step.action for step in plan.steps])

    def test_describe_plan_returns_human_readable_summary(self):
        planner = PlannerEngine()
        plan = planner.plan("open chrome")
        description = planner.describe_plan(plan)

        self.assertIn("Goal: open chrome", description)
        self.assertIn("Estimated complexity: easy", description)
        self.assertIn("Steps:", description)
        self.assertIn("Launch application", description)

    def test_plan_with_invalid_input_returns_none(self):
        planner = PlannerEngine()
        self.assertIsNone(planner.plan(None))
        self.assertIsNone(planner.plan(""))


if __name__ == "__main__":
    unittest.main()
