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

## Multi-Agent Architecture

EchoBrain remains EchoDesk's single entry point while the `agents` framework
coordinates specialized Planner, Coding, Research, Desktop, Vision, and Memory
agents. Agents exchange `AgentTask` and `AgentResult` records through a shared,
thread-safe `AgentContext`; they do not modify one another's internal state.
`AgentRegistry` permits extensions without changes to EchoBrain, and
`AgentScheduler` resolves dependencies, retries failed assignments, and runs
independent work in parallel. Planner conflict resolution selects proposals from
verification status and confidence. Per-agent task, retry, timing, and
verification metrics are available through `EchoBrain.get_agent_metrics()`.
Collaboration diagnostics are stored in `logs/agents.log`.

## Self-Learning and Personalization

`LearningEngine` stores structured outcome metadata through `MemoryEngine` and
ranks strategies by success, verification rate, confidence, usage, and elapsed
time. Planner agents request ranked prior strategies before planning, while
agents contribute safe learning events after work completes. The engine can
recommend plans, workflows, and recovery strategies, and explain selections;
it never modifies code, prompts, approvals, or system configuration. Learning
metrics and preferences are exposed through `EchoBrain.get_learning_summary()`
and diagnostics are recorded in `logs/learning.log`.

## Plugins

Phase 19 provides a backward-compatible plugin framework for extending EchoDesk
without changing core services. `PluginManager` discovers folders containing a
`plugin.py`, validates declarative metadata, resolves dependencies before
initialization, and registers only plugins whose requested permissions are
known. Plugin lifecycle operations include install, enable, disable, unload,
update, reload, and uninstall; a dependency cannot be disabled or removed while
an enabled dependent still needs it.

Plugins are routed by `PluginRegistry` into the Planner and TaskExecutor.
Optional `configure_agents`, `configure_planner`, `configure_learning`, and
`configure_brain` hooks run only after EchoBrain has constructed its services.
Every invocation, failure, and permission denial is retained in the manager's
bounded execution log and written to `logs/plugins.log`; successful and failed
plugin runs are also recorded by LearningEngine when it is available.

The bundled examples are `system_info`, `git`, `github`, `calendar`, and
`file_tools`. They use safe read-only commands by default. Permissions can be
restricted with `PluginPermissions(granted=...)`; execution is denied whenever
a plugin has not been granted every declared permission.

## Performance architecture

Phase 21 keeps startup lightweight by retaining lazy Vision/OCR and optional
plugin loading. `performance/` provides a thread-safe metrics collector,
bounded TTL caches, profiling helper, and repeatable in-process benchmark
runner. Planning templates, OCR/scene results, and plugin discovery metadata
are cached only briefly and with fixed capacities, preventing unbounded memory
growth while preserving the existing APIs.

Independent specialist tasks remain parallelized by the dependency-aware agent
scheduler; dependent tasks are never started early. The performance dashboard
is available through `EchoBrain.get_performance_summary()` and reports startup,
command latency, process memory/CPU, cache statistics, scheduler, plugin, and
Vision metrics. Timing and cache-related diagnostics are written to
`logs/performance.log`.

For comparable release measurements, use `BenchmarkRunner.run(name, workload,
iterations=3)` with a deterministic workload. Benchmarks intentionally do not
perform desktop actions themselves.

## Security and Safety

Phase 20 adds a centralized `SecurityEngine` used by EchoBrain, agents,
ProjectAgent, TaskExecutor, and plugin execution. It classifies actions as low,
medium, or high risk and applies the active configurable policy (`safe`,
`balanced`, or developer-only `unrestricted`). High-risk actions such as file
deletion, installation, system changes, unknown executables, downloaded
scripts, credential access, and policy changes require an explicit approval.

`PermissionManager` enforces fine-grained access for internet, files, desktop
control, processes, clipboard, microphone, camera, plugins, learning, and
memory. `CredentialManager` keeps credentials encrypted in a session-only
vault; names may be listed but secrets are never logged. Security events and
redacted approval decisions are retained in `logs/security.log`. The dashboard
is available through `EchoBrain.get_security_summary()`.

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

Run the complete suite with `python -m pytest` when pytest is available, or
`python -m unittest discover tests` for the standard-library runner.

## Roadmap

**Current Version**

EchoDesk v3.0 (Production)

**Next**

- Desktop Automation
- Voice Intelligence
- Long-Term Memory
- Reflection Engine
- Autonomous Workflows
