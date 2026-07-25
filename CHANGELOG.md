# Changelog

## [3.5.0] - 2026-07-25

### Added

- Phase 19 plugin framework completion: deterministic filesystem discovery, metadata validation, dependency-aware batch installation, lifecycle controls, permission enforcement, and bounded execution logging.
- Safe sample plugins for Git, GitHub guidance, local calendar, and workspace file tools alongside the existing system-information plugin.
- Optional plugin integration hooks for agents, planner, LearningEngine, and EchoBrain.

## [3.4.0] - 2026-07-25

### Added

- Phase 18 safe LearningEngine with persistent structured strategy records, preference reinforcement/decay, workflow reuse, recovery detection, rankings, and explainable recommendations.
- Adaptive PlannerAgent recommendations and EchoBrain learning dashboard summary.

## [3.3.0] - 2026-07-25

### Added

- Phase 17 multi-agent framework with structured task/results, registry, shared context, dependency scheduler, metrics, and learning hooks.
- Planner, Coding, Research, Desktop, Vision, and Memory specialists composed from existing EchoDesk engines.
- EchoBrain collaboration dispatch and agent metrics, with diagnostics in `logs/agents.log`.

## [3.2.0] - 2026-07-25

### Added

- Phase 16 semantic desktop vision: UI models, scene graph, smart control search, relative positioning, scene comparison, and recovery.
- Visual UI actions for desktop automation and optional ProjectAgent scene preparation.
- Application profiles for Explorer, VS Code, Chrome, Edge, Settings, Notepad, and Calculator; cached scenes and `logs/vision.log` diagnostics.

## [3.1.0] - 2026-07-25

### Added

- Phase 15 autonomous `ProjectAgent` orchestration layer.
- Goal queueing, dependencies, background workers, pause/resume/cancel, and progress reports.
- Task-level verification for files, processes, exit codes, OCR, internet output, expected output, and LLM evaluation.
- Bounded automatic recovery with retry history and memory learning.
- Human approval gate for sensitive operations.
- Structured planner metadata for execution order, dependencies, verification, and retry strategy.

## [3.0.0] - 2026-07-24

### Added

- Production release: EchoDesk v3.0
- Centralized configuration (core/config.py)
- Centralized logging with rotation (core/logging_config.py)
- Lazy loading of heavy engines (LLM, Vision, Voice) in TaskExecutor
- Health checks and startup diagnostics
- Scheduler, History, Reflection improvements
- Release packaging stubs and documentation

## [1.0.0] - 2026-07-22

### Added

- Core EchoDesk runtime and architecture.
- Brain routing layer for user command classification.
- Planner module to convert user goals into structured execution plans.
- Agent intelligence module for subsystem selection and decision making.
- Execution Engine to execute plans and track results.
- Vision analysis support with screen context detection and LLM-powered explanations.
- LLM integration layer with provider abstraction and Ollama support.
- Knowledge retrieval engine for local facts and context-aware responses.
- Internet search engine with LLM summarization fallback.
- Runtime integration for plan execution and graceful error handling.
- Memory and workflow orchestration support.
- Validation suite with 44 passing unittests.
