from __future__ import annotations
from typing import Any

from planner.planner import PlanStep


class ExecutionStepExecutor:
    """A generic step executor using injected subsystem references."""

    def __init__(self, tool_registry: dict[str, Any] | None = None) -> None:
        self.tool_registry = tool_registry or {}

    def execute_step(self, step: PlanStep) -> dict[str, Any]:
        """Execute a single plan step through the injected tools."""
        if not isinstance(step, PlanStep):
            return {"success": False, "message": "Invalid step object."}

        action = (step.action or "").strip().lower()
        if not action:
            return {"success": False, "message": "Step action is missing."}

        mapping = self._resolve_mapping(action)
        if mapping is None:
            return {"success": False, "message": f"No handler available for step action: {step.action}."}

        tool_name, method_name = mapping
        tool = self.tool_registry.get(tool_name)
        if tool is None:
            return {"success": False, "message": f"Tool '{tool_name}' is not available."}

        method = getattr(tool, method_name, None)
        if not callable(method):
            return {"success": False, "message": f"Method '{method_name}' not found on tool '{tool_name}'."}

        try:
            if action in ("capture screen", "analyze image"):
                return method()

            if action == "return summary":
                if hasattr(self.tool_registry.get("LLMEngine"), "ask"):
                    return method(step.description)
                return {"success": False, "message": "LLM engine unavailable for summary."}

            if action == "wait":
                duration = str(step.tool or "").strip()
                if duration and duration.replace('.', '', 1).isdigit():
                    return method(duration)
                return {"success": True, "message": f"Skipped wait step with non-numeric duration: {step.description}."}

            if action in ("launch application", "open website", "type text", "press key", "hotkey", "move mouse", "click mouse", "scroll"):
                return method(step.tool)

            if action == "search internet" or action == "search website":
                return method(step.tool)

            if action in ("summarize results", "recommend fix", "summarize page"):
                prompt = f"{step.description}\nDetails: {step.tool or ''}".strip()
                return method(prompt)

            if action == "capture memory":
                return method(step.tool, step.description)

            if action == "verify memory":
                return method(step.tool)

            # Default to passing the step payload when possible.
            return method(step.tool)
        except TypeError as exc:
            return {"success": False, "message": f"Invalid arguments for '{method_name}': {exc}"}
        except Exception as exc:
            return {"success": False, "message": f"Step execution raised an exception: {type(exc).__name__}: {exc}"}

    def _resolve_mapping(self, action: str) -> tuple[str, str] | None:
        mappings: dict[str, tuple[str, str]] = {
            "launch application": ("AutomationEngine", "open_application"),
            "open website": ("AutomationEngine", "open_website"),
            "wait": ("AutomationEngine", "wait"),
            "type text": ("AutomationEngine", "type_text"),
            "press key": ("AutomationEngine", "press_key"),
            "hotkey": ("AutomationEngine", "hotkey"),
            "move mouse": ("AutomationEngine", "move_mouse"),
            "click mouse": ("AutomationEngine", "click_mouse"),
            "scroll": ("AutomationEngine", "scroll"),
            "capture screen": ("Vision", "read_screen"),
            "analyze image": ("Vision", "read_screen"),
            "return summary": ("LLMEngine", "ask"),
            "search internet": ("InternetEngine", "search"),
            "search website": ("InternetEngine", "search"),
            "summarize results": ("LLMEngine", "ask"),
            "recommend fix": ("LLMEngine", "ask"),
            "verify memory": ("MemoryEngine", "retrieve_fact"),
            "capture memory": ("MemoryEngine", "remember_fact"),
            "summarize page": ("LLMEngine", "ask"),
        }

        for key, value in mappings.items():
            if action == key or action.startswith(key):
                return value
        return None
