# Changelog

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
