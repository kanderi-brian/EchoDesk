import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, List
from performance.metrics import TTLCache


class ExecutionStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class Task:
    id: str
    description: str
    capability: str
    status: ExecutionStatus = field(default_factory=lambda: ExecutionStatus.PENDING)
    result: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "capability": self.capability,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
        }


@dataclass
class PlanStep:
    id: str
    tool: str
    action: str
    description: str
    expected_result: str
    optional: bool = False
    status: str = "pending"
    engine: str = "unknown"
    retry_count: int = 0
    dependencies: list[str] = field(default_factory=list)
    duration: float | None = None
    result: str | None = None
    verification_method: str = "expected_output"
    retry_strategy: str = "retry"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tool": self.tool,
            "action": self.action,
            "description": self.description,
            "expected_result": self.expected_result,
            "optional": self.optional,
            "status": self.status,
            "engine": self.engine,
            "retry_count": self.retry_count,
            "dependencies": list(self.dependencies),
            "duration": self.duration,
            "result": self.result,
            "verification_method": self.verification_method,
            "retry_strategy": self.retry_strategy,
        }


@dataclass
class ExecutionPlan:
    goal: str
    steps: List[PlanStep] = field(default_factory=list)
    tasks: List[Task] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    estimated_complexity: str = "unknown"
    requires_confirmation: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    reasoning: str = ""
    required_tools: List[str] = field(default_factory=list)
    expected_result: str = ""
    execution_order: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.original_request = self.goal

    def add_step(self, step: PlanStep) -> None:
        self.steps.append(step)

    def add_task(self, task: Task) -> None:
        self.tasks.append(task)

    def next_step(self) -> PlanStep | None:
        for step in self.steps:
            if step.status == "pending":
                return step
        return None

    def is_complete(self) -> bool:
        if not self.steps:
            return True
        return all(step.status == "completed" for step in self.steps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "steps": [step.to_dict() for step in self.steps],
            "tasks": [task.to_dict() for task in self.tasks],
            "estimated_complexity": self.estimated_complexity,
            "requires_confirmation": self.requires_confirmation,
            "created_at": self.created_at.isoformat(),
            "reasoning": self.reasoning,
            "required_tools": list(self.required_tools),
            "expected_result": self.expected_result,
            "execution_order": list(self.execution_order),
        }


class PlannerEngine:
    """A reusable planner engine for EchoDesk.

    PlannerEngine accepts a user goal and converts it into an ordered,
    structured execution plan. It never executes actions itself.
    """

    def __init__(self, automation_engine: Any | None = None, learning_engine: Any | None = None, plugin_registry: Any | None = None):
        """Initialize the planner engine.

        Args:
            automation_engine: Optional automation engine instance used for
                validating automation-related plans without executing them.
            learning_engine: Optional learning engine providing preferences.
            plugin_registry: Optional PluginRegistry instance for plugin-aware planning.
        """
        self.automation_engine = automation_engine
        self.learning_engine = learning_engine
        self.plugin_registry = plugin_registry
        # Plans are immutable templates to callers: cached entries are cloned before return.
        self._plan_cache = TTLCache(ttl=120.0, maxsize=128, name="planner")

    def set_plugin_registry(self, registry: Any | None) -> None:
        self.plugin_registry = registry

    def receive_feedback(self, feedback: dict[str, Any]) -> None:
        if not feedback:
            return
        if not hasattr(self, "feedback_history"):
            self.feedback_history = []
        self.feedback_history.append(feedback)

    def plan(self, command: str) -> ExecutionPlan | None:
        """Translate a user goal into a structured execution plan.

        Args:
            command: The user request.

        Returns:
            An ExecutionPlan instance or None when the request cannot be
            planned.
        """
        if not isinstance(command, str):
            return None

        cached = self._plan_cache.get(command.strip().casefold())
        if cached is not None:
            import copy
            return copy.deepcopy(cached)

        text = command.strip().lower()
        if not text:
            return None

        # If a plugin registry is available and a plugin supports this command,
        # create a plan that executes the plugin instead of built-in engines.
        try:
            if self.plugin_registry is not None and self.plugin_registry.supports(command):
                # Create a plan with a single task that delegates to Plugin capability
                plan = ExecutionPlan(goal=command)
                plan.add_task(Task(id=str(uuid.uuid4()), description="Execute plugin capable of handling the command.", capability="Plugin"))
                plan.required_capabilities = ["Plugin"]
                plan.reasoning = "Handled by plugin"
                return plan
        except Exception:
            # If plugin registry check fails, fall back to normal planning
            pass

        if getattr(self, "feedback_history", None):
            last_feedback = self.feedback_history[-1]
            if last_feedback.get("command") == command and last_feedback.get("replan_recommended"):
                rebased_plan = ExecutionPlan(goal=command)
                rebased_plan.add_task(Task(
                    id=str(uuid.uuid4()),
                    description="Retry the request with the LLM after reflection feedback.",
                    capability="LLM",
                ))
                rebased_plan.required_capabilities = ["LLM"]
                rebased_plan.reasoning = "Replan after reflection feedback"
                return rebased_plan

        routines = [
            self._plan_open_app_and_search,
            self._plan_open_application,
            self._plan_open_website,
            self._plan_search_and_summarize,
            self._plan_generic_internet_search,
            self._plan_generic_memory_command,
            self._plan_generic_knowledge_query,
            self._plan_generic_vision_command,
            self._plan_generic_voice_command,
            self._plan_search_documentation,
            self._plan_fix_python_error,
            self._plan_remember_conversation,
            self._plan_read_screen,
            self._plan_organize_downloads,
            self._plan_organize_desktop,
            self._plan_summarize_document,
            self._plan_create_folder,
            self._plan_time_query,
            self._plan_wait,
            self._plan_move_mouse,
            self._plan_click_mouse,
            self._plan_scroll,
            self._plan_hotkey,
            self._plan_press_key,
            self._plan_type_text,
        ]

        for routine in routines:
            steps = routine(text)
            if steps is not None:
                plan = self._build_plan(command, steps)
                self._plan_cache.set(command.strip().casefold(), plan)
                import copy
                return copy.deepcopy(plan)

        return None

    def describe_plan(self, plan: ExecutionPlan | dict[str, Any]) -> str:
        """Return a human-readable description of a plan.

        Args:
            plan: The structured execution plan.

        Returns:
            A summary of plan details and ordered steps.
        """
        if not plan:
            return "I could not generate a plan for that request."

        if isinstance(plan, ExecutionPlan):
            steps = plan.steps
            goal = plan.goal
            reasoning = plan.reasoning
            complexity = plan.estimated_complexity
            required_tools = plan.required_tools
            expected_result = plan.expected_result
        else:
            steps = plan.get("steps", [])
            goal = plan.get("goal", "")
            reasoning = plan.get("reasoning", "")
            complexity = plan.get("estimated_complexity", "unknown")
            required_tools = plan.get("required_tools", [])
            expected_result = plan.get("expected_result", "")

        lines = [f"Goal: {goal}", f"Reasoning: {reasoning}"]
        lines.append(f"Estimated complexity: {complexity}")
        lines.append(f"Required tools: {', '.join(required_tools) or 'none'}")
        lines.append(f"Expected result: {expected_result}")

        lines.append("Steps:")
        for index, step in enumerate(steps, start=1):
            if isinstance(step, PlanStep):
                description = step.description or self._format_step(step.to_dict())
            else:
                description = step.get("description") or self._format_step(step)
            lines.append(f"{index}. {description}")

        if isinstance(plan, ExecutionPlan) and plan.tasks:
            lines.append("Tasks:")
            for idx, task in enumerate(plan.tasks, start=1):
                lines.append(f"{idx}. [{task.capability}] {task.description} ({task.status.value})")

        return "\n".join(lines)

    def is_planning_command(self, command: str) -> bool:
        """Determine whether the command is suitable for planning."""
        return self.plan(command) is not None

    def _build_plan(self, command: str, steps: list[PlanStep]) -> ExecutionPlan:
        goal = command.strip()
        reasoning = self._infer_reasoning(command, steps)
        complexity = self._estimate_complexity(steps)
        capabilities = self._infer_capabilities(command)
        tools = self._infer_tools(steps) or [cap.lower() for cap in capabilities]
        expected_result = self._infer_expected_result(command, steps)
        requires_confirmation = any(step.optional for step in steps) or complexity != "easy"

        for index, step in enumerate(steps):
            if not step.engine or step.engine == "unknown":
                step.engine = capabilities[0] if capabilities else "LLM"
            if not step.dependencies and index:
                step.dependencies = [steps[index - 1].id]
            if step.engine.lower().startswith("internet"):
                step.verification_method = "internet_response"

        tasks = self._build_tasks(steps, capabilities)
        plan = ExecutionPlan(
            goal=goal,
            steps=steps,
            tasks=tasks,
            required_capabilities=sorted({task.capability for task in tasks}) if tasks else capabilities,
            estimated_complexity=complexity,
            requires_confirmation=requires_confirmation,
            reasoning=reasoning,
            required_tools=tools,
            expected_result=expected_result,
            execution_order=[step.id for step in steps],
        )
        return plan

    def _infer_engine(self, action: str) -> str:
        action = action.strip().lower()
        if any(keyword in action for keyword in ("launch application", "open website", "wait", "type text", "press key", "hotkey", "move mouse", "click mouse", "scroll")):
            return "AutomationEngine"
        if any(keyword in action for keyword in ("capture screen", "analyze image", "return summary", "read screen", "screen")):
            return "Vision"
        if "search internet" in action or "search website" in action or "search" in action and "internet" in action:
            return "InternetEngine"
        if any(keyword in action for keyword in ("summarize", "recommend fix", "resolve", "explain")):
            return "LLMEngine"
        if any(keyword in action for keyword in ("memory", "remember", "verify memory")):
            return "MemoryEngine"
        return "Unknown"

    def _infer_reasoning(self, command: str, steps: list[dict[str, str]]) -> str:
        return f"Break the goal into the necessary actions to satisfy: {command.strip()}."

    def _estimate_complexity(self, steps: list[dict[str, str]]) -> str:
        if len(steps) <= 2:
            return "easy"
        if len(steps) <= 4:
            return "medium"
        return "hard"

    def _infer_tools(self, steps: list[PlanStep]) -> list[str]:
        tools = set()
        for step in steps:
            action = step.action.lower()
            if "application" in action or "launch" in action:
                tools.add("automation")
            if "website" in action or "browser" in action:
                tools.add("browser")
            if "screen" in action or "image" in action:
                tools.add("vision")
            if "document" in action or "summarize" in action:
                tools.add("document")
            if "folder" in action or "create" in action:
                tools.add("file system")
            if "wait" in action:
                tools.add("timer")
            if "mouse" in action or "click" in action or "scroll" in action:
                tools.add("input")
            if "type" in action or "press" in action or "hotkey" in action:
                tools.add("keyboard")
        return sorted(tools)

    def _task(self, description: str, capability: str) -> Task:
        return Task(id=str(uuid.uuid4()), description=description, capability=capability)

    def _build_tasks(self, steps: list[PlanStep], capabilities: list[str]) -> list[Task]:
        tasks: list[Task] = []
        for step in steps:
            capability = "LLM"
            if step.engine and "internet" in step.engine.lower():
                capability = "Internet"
            elif step.engine and "knowledge" in step.engine.lower():
                capability = "Knowledge"
            elif step.engine and "memory" in step.engine.lower():
                capability = "Memory"
            elif step.engine and "vision" in step.engine.lower():
                capability = "Vision"
            elif step.engine and "voice" in step.engine.lower():
                capability = "Voice"
            else:
                inferred = self._infer_capabilities(step.action)
                if inferred:
                    capability = inferred[0]
                elif capabilities:
                    capability = capabilities[0]
            tasks.append(self._task(step.description, capability))
        return tasks

    def _infer_capabilities(self, command: str) -> list[str]:
        normalized = command.strip().lower()

        if any(keyword in normalized for keyword in ("image", "screenshot", "screen", "describe this")):
            return ["Vision"]
        if any(keyword in normalized for keyword in ("listen", "say", "speak", "voice", "microphone", "wake", "hello", "hi")):
            return ["Voice"]
        if any(keyword in normalized for keyword in ("remember", "history", "recall", "what do you remember", "what do you know")):
            return ["Memory"]
        if any(keyword in normalized for keyword in ("weather", "news", "search")):
            return ["Internet"]
        if any(keyword in normalized for keyword in ("what is my", "what are my", "tell me about my", "what do i know about", "what do you know about my", "do i have")):
            return ["Memory"]
        if self._prefers_programming_knowledge(normalized):
            return ["Knowledge"]
        if any(keyword in normalized for keyword in ("what is", "explain", "define", "describe", "who is", "who are", "why is", "how does", "knowledge", "lookup")):
            return ["Knowledge"]

        return ["LLM"]

    def _prefers_programming_knowledge(self, normalized: str) -> bool:
        if self.learning_engine is None:
            return False

        try:
            preferences = self.learning_engine.get_preferences()
        except Exception:
            return False

        for pref in preferences:
            if pref.category.lower() == "language" and pref.key.lower() == "programming language" and pref.value.lower() == "python" and pref.confidence >= 0.4:
                if "python" in normalized and "news" not in normalized and "search" not in normalized:
                    return True
        return False

    def _prefers_voice(self, normalized: str) -> bool:
        if self.learning_engine is None:
            return False

        try:
            preferences = self.learning_engine.get_preferences()
        except Exception:
            return False

        for pref in preferences:
            if pref.category.lower() == "interaction mode" and pref.value.lower() == "voice" and pref.confidence >= 0.4:
                return True
        return False

    def _prefers_vision(self, normalized: str) -> bool:
        if self.learning_engine is None:
            return False

        try:
            preferences = self.learning_engine.get_preferences()
        except Exception:
            return False

        for pref in preferences:
            if pref.category.lower() == "preferred tool" and pref.value.lower() == "vision" and pref.confidence >= 0.4:
                return True
        return False

    def _infer_expected_result(self, command: str, steps: list[PlanStep]) -> str:
        normalized = command.strip().lower()
        if "open" in normalized and "search" in normalized:
            return "The application opens and performs the search."
        if "read" in normalized and "screen" in normalized:
            return "A summary of the screen contents is provided."
        if "time" in normalized:
            return "The current system time is returned."
        if "summarize" in normalized:
            return "A short summary of the requested content is returned."
        if "organize" in normalized:
            return "Files or desktop items are arranged neatly."
        if "create a folder" in normalized or "create folder" in normalized:
            return "A new folder is created with the requested name."
        return "The requested task is planned and ready for execution."

    def _plan_open_app_and_search(self, text: str) -> list[PlanStep] | None:
        match = re.match(
            r"^(?:open|launch|start)\s+(?:application\s+)?(?P<app>.+?)\s+and\s+search\s+(?P<query>.+)$",
            text,
        )
        if not match:
            return None

        app = self._normalize_application(match.group("app"))
        query = match.group("query").strip()

        return [
            self._step("Launch application", app, f"Launch application: {app}."),
            self._step("Wait", "application", "Wait until the application opens."),
            self._step("Focus search bar", "search field", "Bring the search bar into focus."),
            self._step("Type text", query, f"Type \"{query}\"."),
            self._step("Press key", "Enter", "Press Enter to execute the search."),
        ]

    def _plan_open_application(self, text: str) -> list[PlanStep] | None:
        match = re.match(r"^(?:open|launch|start)\s+(?:application\s+)?(?P<app>.+)$", text)
        if not match:
            return None

        app = self._normalize_application(match.group("app"))
        return [
            self._step("Launch application", app, f"Launch application: {app}."),
            self._step("Wait", "application", "Wait until the application opens."),
        ]

    def _plan_open_website(self, text: str) -> list[PlanStep] | None:
        match = re.match(
            r"^(?:open|visit|go to|navigate to)\s+(?:website\s+)?(?P<url>https?://\S+|www\.\S+|\S+\.\S+)$",
            text,
        )
        if not match:
            return None
 
        url = match.group("url").strip()
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
 
        return [
            self._step("Open website", url, f"Open website: {url}."),
            self._step("Wait", "browser", "Wait until the browser opens the website."),
        ]
 
    def _plan_search_and_summarize(self, text: str) -> list[PlanStep] | None:
        if re.search(r"\b(search|find|browse)\b.*\b(summariz|summary|summarise)\b", text) or (
            "search" in text and "summarize" in text
        ):
            return [
                self._step("Search internet", text, "Search the internet for the requested topic."),
                self._step("Summarize results", "search results", "Summarize the internet findings using the language model."),
            ]
        return None

    def _plan_generic_internet_search(self, text: str) -> list[PlanStep] | None:
        if re.search(r"\b(search|weather|news|browse|find)\b", text):
            return [
                self._step("Search internet", text, "Use the internet engine to search for the user request."),
            ]
        return None
 
    def _plan_generic_knowledge_query(self, text: str) -> list[PlanStep] | None:
        if re.search(r"\b(what is|explain|define|describe|who is|who are|why is)\b", text):
            return [
                self._step("Lookup knowledge", text, "Use the knowledge engine to answer the question."),
            ]
        return None
 
    def _plan_generic_memory_command(self, text: str) -> list[PlanStep] | None:
        if re.search(
            r"\b(remember|recall|what do you remember|what do i remember|what is my|what are my|tell me about my|what do you know about my|do i have|what do i know about|forget|delete|remove)\b",
            text,
        ):
            return [
                self._step("Manage memory", text, "Use the memory engine to store, recall, or manage memory."),
            ]
        return None
 
    def _plan_generic_vision_command(self, text: str) -> list[PlanStep] | None:
        if re.search(r"\b(image|screenshot|screen|describe this|describe)\b", text):
            return [
                self._step("Analyze screen", text, "Use the vision engine to inspect or describe screen content."),
            ]
        return None
 
    def _plan_generic_voice_command(self, text: str) -> list[PlanStep] | None:
        if re.search(r"\b(listen|say|speak|voice|microphone|wake|hello|hi|good morning|good evening)\b", text):
            action = "Listen for voice command" if re.search(r"\b(listen|wake|microphone)\b", text) else "Speak response"
            description = "Use the voice engine to capture or vocalize audio." if action.startswith("Listen") else "Use the voice engine to vocalize a response."
            return [
                self._step(action, text, description),
            ]
        return None
 
    def _plan_search_documentation(self, text: str) -> list[PlanStep] | None:
        if "search" in text and ("python documentation" in text or "python docs" in text):
            query = "python documentation"
            return [
                self._step("Open website", "https://www.python.org/doc/", "Open the Python documentation website."),
                self._step("Search website", query, "Search the Python documentation for the requested topic."),
                self._step("Summarize page", "documentation", "Summarize the key documentation results."),
            ]
        return None
 
    def _plan_fix_python_error(self, text: str) -> list[PlanStep] | None:
        if "fix" in text and "python" in text and ("error" in text or "importerror" in text or "exception" in text):
            return [
                self._step("Capture screen", "screen", "Capture the screen to inspect the error output.", optional=True),
                self._step("Analyze image", "error output", "Analyze the screen or error text to identify the failure."),
                self._step("Search internet", "error details", "Search the internet for the Python error and traceback."),
                self._step("Summarize results", "web findings", "Summarize the troubleshooting guidance for the Python error."),
                self._step("Recommend fix", "fix suggestion", "Recommend the most likely fix or next steps.", optional=True),
            ]
        return None
 
    def _plan_remember_conversation(self, text: str) -> list[PlanStep] | None:
        if "remember" in text and "conversation" in text:
            return [
                self._step("Capture memory", "conversation", "Capture the conversation details into memory."),
                self._step("Verify memory", "memory store", "Confirm the conversation was remembered successfully.", optional=True),
            ]
        return None
 
    def _plan_read_screen(self, text: str) -> list[PlanStep] | None:
        if text in (
            "read my screen",
            "read screen",
            "what do you see",
            "analyze my screen",
            "analyze screen",
        ):
            return [
                self._step("Capture screen", "screen", "Capture the screen."),
                self._step("Analyze image", "image", "Analyze the captured image."),
                self._step("Return summary", "summary", "Return a concise summary of the screen contents."),
            ]
        return None

    def _plan_organize_downloads(self, text: str) -> list[PlanStep] | None:
        if "organize" in text and "download" in text:
            return [
                self._step("Open folder", "Downloads", "Open the Downloads folder."),
                self._step("Sort files", "Downloads", "Sort downloaded files by type or date."),
                self._step("Move files", "organized folders", "Move files into appropriate folders."),
                self._step("Review result", "folder layout", "Review the organized Downloads folder."),
            ]
        return None

    def _plan_organize_desktop(self, text: str) -> list[PlanStep] | None:
        if "organize" in text and "desktop" in text:
            return [
                self._step("Scan desktop", "Desktop", "Scan desktop icons and files."),
                self._step("Group items", "Desktop", "Group similar items together."),
                self._step("Create folders", "Desktop folders", "Create folders for organization."),
                self._step("Move items", "folders", "Move items into the appropriate folders."),
                self._step("Review", "Desktop layout", "Review the organized desktop."),
            ]
        return None

    def _plan_summarize_document(self, text: str) -> list[PlanStep] | None:
        if "summarize" in text and "document" in text:
            return [
                self._step("Locate document", "document", "Locate the document to summarize."),
                self._step("Read document", "document", "Read the document contents."),
                self._step("Extract key points", "document", "Identify the most important points."),
                self._step("Write summary", "summary", "Write a concise summary."),
            ]
        return None

    def _plan_create_folder(self, text: str) -> list[PlanStep] | None:
        match = re.match(r"^(?:create|make)\s+(?:a\s+)?folder\s+(?:called\s+)?(?P<name>.+)$", text)
        if not match:
            return None

        folder_name = match.group("name").strip().title()
        return [
            self._step("Create folder", folder_name, f"Create a folder called {folder_name}."),
            self._step("Verify folder", folder_name, "Verify that the folder has been created."),
        ]

    def _plan_time_query(self, text: str) -> list[PlanStep] | None:
        if text in (
            "what time is it",
            "what is the time",
            "tell me the time",
            "current time",
            "time",
        ):
            return [
                self._step("Ask system clock", "clock", "Ask the system clock for the current time."),
                self._step("Return time", "time", "Return the formatted current time."),
            ]
        return None

    def _plan_wait(self, text: str) -> list[PlanStep] | None:
        match = re.match(r"^(?:wait|sleep|pause)\s+(?P<seconds>\d+(?:\.\d+)?)\s*(?:seconds?)?$", text)
        if not match:
            return None

        value = match.group("seconds")
        return [
            self._step("Wait", value, f"Wait for {value} seconds."),
        ]

    def _plan_move_mouse(self, text: str) -> list[PlanStep] | None:
        match = re.match(
            r"^(?:move mouse to|move the mouse to|move mouse)\s+(?P<x>-?\d+)\s*(?:,|and| )\s*(?P<y>-?\d+)$",
            text,
        )
        if not match:
            return None

        return [
            self._step("Move mouse", f"{match.group('x')},{match.group('y')}", f"Move mouse to ({match.group('x')}, {match.group('y')})."),
        ]

    def _plan_click_mouse(self, text: str) -> list[PlanStep] | None:
        match = re.match(
            r"^(?:click|double click|right click|middle click)(?:\s+(?P<button>left|right|middle))?(?:\s+at\s+(?P<x>-?\d+)\s*(?:,|and)\s*(?P<y>-?\d+))?$",
            text,
        )
        if not match:
            return None

        button = (match.group("button") or "left").strip()
        target = "" if not match.group("x") else f"{match.group('x')},{match.group('y')}"
        description = f"Click {button} mouse button"
        if target:
            description += f" at ({target.replace(',', ', ')})"
        description += "."

        return [
            self._step("Click mouse", target or button, description),
        ]

    def _plan_scroll(self, text: str) -> list[PlanStep] | None:
        match = re.match(r"^scroll\s+(?P<amount>-?\d+)\s*(?:lines?)?$", text)
        if not match:
            return None

        return [
            self._step("Scroll", match.group("amount"), f"Scroll by {match.group('amount')} units."),
        ]

    def _plan_hotkey(self, text: str) -> list[PlanStep] | None:
        match = re.match(
            r"^(?:press|hit|tap)\s+(?P<keys>(?:ctrl|alt|shift|control)(?:\+|\s+)(?:\w+)(?:\s*(?:\+|\s+)\w+)*)$",
            text,
        )
        if not match:
            return None

        combination = re.sub(r"\s+", "+", match.group("keys").strip())
        return [
            self._step("Hotkey", combination, f"Press hotkey: {combination}."),
        ]

    def _plan_press_key(self, text: str) -> list[PlanStep] | None:
        match = re.match(r"^(?:press|tap)\s+(?:the\s+)?(?P<key>.+)$", text)
        if not match:
            return None

        key = match.group("key").strip()
        return [
            self._step("Press key", key, f"Press key: {key}."),
        ]

    def _plan_type_text(self, text: str) -> list[PlanStep] | None:
        match = re.match(r"^(?:type|enter)\s+(?P<text>.+)$", text)
        if not match:
            return None

        payload = match.group("text").strip()
        return [
            self._step("Type text", payload, f"Type \"{payload}\"."),
        ]

    def _normalize_application(self, app: str) -> str:
        normalized = app.strip().lower()
        normalized = re.sub(r"^(?:the\s+)?", "", normalized)
        if normalized.endswith(" browser"):
            normalized = normalized[: -len(" browser")]
        if normalized.startswith("google "):
            normalized = normalized[len("google ") :]

        if normalized in ("chrome", "google chrome"):
            return "Chrome"
        if normalized in ("firefox", "mozilla firefox"):
            return "Firefox"
        if normalized in ("edge", "microsoft edge"):
            return "Microsoft Edge"
        if normalized in ("notepad", "notepad++"):
            return normalized.title()
        return normalized.title()

    def _step(
        self,
        action: str,
        target: str,
        description: str,
        expected_result: str = "",
        optional: bool = False,
    ) -> PlanStep:
        step_id = uuid.uuid4().hex[:8]
        return PlanStep(
            id=step_id,
            tool=target,
            action=action,
            description=description,
            expected_result=expected_result or description,
            optional=optional,
            engine=self._infer_engine(action),
        )

    def _format_step(self, step: PlanStep | dict[str, str]) -> str:
        if isinstance(step, PlanStep):
            target = step.tool
            action = step.action
        else:
            target = step.get("target")
            action = step.get("action")

        if target:
            return f"{action}: {target}."
        return action or "Perform action."
