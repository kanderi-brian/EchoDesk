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
