"""EchoDesk entrypoint."""

from brain.brain import EchoBrain


def main() -> None:
    """Run a Phase 12 demonstration of the unified intelligence runtime."""
    brain = EchoBrain()

    queries = [
        "Search today's AI news and summarize it.",
        "Remember my favorite language is Python.",
        "What is my favorite language?",
        "Explain object-oriented programming.",
    ]

    print("EchoDesk initialized successfully.")
    print()

    for query in queries:
        print("User:")
        print(query)
        print()

        response = brain.process(query, return_structured=True)
        if isinstance(response, dict):
            plan = response.get("plan")
            result = response.get("details")
            final_response = response.get("final_response")
        else:
            plan = None
            result = None
            final_response = str(response)

        print("Plan:")
        if plan is not None:
            print(f"  Goal: {plan.goal}")
            print(f"  Capabilities: {plan.required_capabilities}")
            if getattr(plan, "tasks", None):
                print("  Tasks:")
                for index, task in enumerate(plan.tasks, start=1):
                    print(f"    {index}. [{task.capability}] {task.description} - {task.status.value}")
            else:
                print("  Steps:")
                for step in plan.steps:
                    print(f"    - {step.description}")
        else:
            print("  No plan available.")

        print("Execution report:")
        if result is not None:
            print(f"  Status: {result.status}")
            print(f"  Engines used: {result.engines_used}")
            print(f"  Execution time: {result.execution_time:.2f}s" if result.execution_time is not None else "  Execution time: unknown")
            if result.logs:
                print("  Logs:")
                for log in result.logs:
                    print(f"    - {log}")
        else:
            print("  No execution details available.")

        print("Final response:")
        print(final_response)
        print("-" * 60)

    summary = brain.memory_engine.summary()
    print("Memory Summary:")
    print(f"  Conversations: {summary.total_conversations}")
    print(f"  Facts: {summary.total_facts}")
    print(f"  Latest interaction: {summary.latest_interaction}")


if __name__ == "__main__":
    main()
