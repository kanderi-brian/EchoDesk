import unittest

from planner.planner import PlannerEngine


class TestPlannerMemoryRouting(unittest.TestCase):
    def test_memory_command_routes_to_memory(self):
        planner = PlannerEngine()
        memory_commands = [
            "Remember my name is Brian.",
            "What is my name?",
            "What are my favorite languages?",
            "Tell me about my preferences.",
            "What do you know about my settings?",
        ]

        for command in memory_commands:
            with self.subTest(command=command):
                plan = planner.plan(command)
                self.assertIsNotNone(plan)
                self.assertEqual(plan.required_capabilities, ["Memory"])
                self.assertTrue(any("memory" in step.description.lower() for step in plan.steps))

    def test_knowledge_command_still_uses_knowledge(self):
        planner = PlannerEngine()
        plan = planner.plan("What is Python?")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.required_capabilities, ["Knowledge"])
        self.assertTrue(any("knowledge" in step.description.lower() for step in plan.steps))


if __name__ == "__main__":
    unittest.main()
