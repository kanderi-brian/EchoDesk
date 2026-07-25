# EchoDesk

EchoDesk is a modular AI desktop assistant designed to understand the user's desktop environment, reason about goals, and execute plans across connected subsystems. It combines knowledge retrieval, internet search, screen analysis, execution planning, memory, workflow orchestration, and automation to support intelligent desktop interactions.

## Capabilities

EchoDesk provides the following capabilities:

• Planning
• Reasoning
• Internet search
• Knowledge retrieval
• Vision analysis
• Execution planning
• Execution engine
• Memory
• Workflow orchestration

## Desktop Vision

Phase 16 adds a semantic desktop-vision pipeline: screen capture, window and
control detection, selective OCR, icon/profile cues, and scene-graph assembly.
`VisionEngine.capture_scene()` returns a `UIScene` containing `UIWindow` and
`UIElement` objects with labels, confidence, bounds, state, and parent/child
relationships. `find_element("Save button")` resolves controls by meaning;
relative checks support relationships such as controls below a field or inside
a toolbar. `compare_scene()` and `verify_change()` provide visual verification
after an action, while recovery retries labels and hierarchy before giving up.

Desktop controllers can act on UI elements (`click_element`,
`type_into_element`, `scroll_container`) so coordinates remain an implementation
detail. Scene data is cached by screen hash and vision diagnostics are recorded
in `logs/vision.log`.

## Autonomous Project Agent

`ProjectAgent` adds an autonomous orchestration layer over the existing Brain,
Planner, TaskExecutor, MemoryEngine, and desktop engines. It accepts high-level
goals, classifies them as coding, desktop automation, research, or mixed work,
then creates ordered tasks with dependencies and verification methods.

Goals can be queued, reordered, paused, resumed, cancelled, or run in the
background. Each task is executed through the existing `TaskExecutor`, verified
by `VerificationEngine`, and retried up to its configured limit. The agent keeps
an execution history and records successful and failed strategies in memory.

`VerificationEngine` supports expected-output matching, file existence, process
status, exit codes, OCR text, internet-response checks, and optional LLM review.
Sensitive operations (for example deletion, software installation, system
settings, formatting, or unknown scripts) pause for explicit approval.

For coding goals, `ProjectAgent.inspect_project()` inspects the repository,
README, requirements, tests, and Git metadata before work is dispatched. The
brain exposes non-breaking autonomous status through `brain.get_progress()` and
queues work through `brain.submit_project_goal()`.

## Architecture

The EchoDesk pipeline is organized as a layered, modular system:

User
↓
EchoBrain
↓
Router
↓
TaskExecutor
↓
Planner
↓
Agent
↓
ExecutionEngine
↓
Tool Registry
↓
Knowledge
Internet
Vision
Memory
Desktop
Automation
Voice

Each stage separates responsibilities so the assistant can route commands, build plans, select the right subsystem, and execute actions reliably.

## Installation

1. Install Python 3.11 or later.
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # macOS/Linux
   venv\Scripts\activate    # Windows
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run EchoDesk:
   ```bash
   python main.py
   ```

## Testing

Run the validation suite with:

```bash
python -m unittest discover tests
```

The current validation suite contains 44 passing tests.

## Roadmap

**Current Version**

EchoDesk v3.0 (Production)

**Next**

- Desktop Automation
- Voice Intelligence
- Long-Term Memory
- Reflection Engine
- Autonomous Workflows
