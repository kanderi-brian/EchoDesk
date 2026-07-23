"""
EchoDesk v2.0 Runtime Integration - Central Application Class

This module provides the unified entry point for EchoDesk, initializing and
managing all subsystems including memory, knowledge, voice, vision, and
desktop automation.
"""

import logging
import threading
from typing import Any, Dict, Optional

# Core modules
from brain.brain import EchoBrain
from memory.manager import MemoryManager
from memory.storage import MemoryStorage
from memory.controller import MemoryController
from memory.retrieval import MemoryRetrieval
from memory.search import MemorySearch
from knowledge.knowledge import KnowledgeEngine
from internet.internet import InternetEngine
from llm.engine import LLMEngine
from llm.provider import BaseLLMProvider
from llm.ollama_provider import OllamaProvider

# Vision and Voice
from vision.capture import ScreenCapture
from vision.reader import ScreenReader
from vision.analyzer import ScreenAnalyzer
from voice.controller import VoiceController

# Desktop automation
from desktop.controller import DesktopController
from desktop.launcher import ApplicationLauncher
from desktop.window import WindowManager
from desktop.mouse import MouseController
from desktop.keyboard import KeyboardController
from desktop.clipboard import ClipboardManager

# Execution and Planning
from execution.executor import ExecutionStepExecutor
from execution.engine import ExecutionEngine
from planner.planner import PlannerEngine
from brain.router import Router

# Configuration
from context.context import get_context_engine


class EchoDesk:
    """
    Central orchestrator for EchoDesk v2.0.

    Manages initialization, dependency injection, and lifecycle of all
    EchoDesk subsystems. Provides a single, unified interface for the
    application.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize EchoDesk with all subsystems.

        Args:
            config: Optional configuration dictionary for customizing behavior.
        """
        self.config = config or {}
        self._lock = threading.RLock()
        self._running = False
        self._initialized = False

        # Setup logging
        self.logger = self._setup_logging()
        self.logger.info("Initializing EchoDesk v2.0...")

        # Storage and Memory
        self.memory_storage: Optional[MemoryStorage] = None
        self.memory_manager: Optional[MemoryManager] = None
        self.memory_controller: Optional[MemoryController] = None

        # Knowledge and LLM
        self.knowledge_engine: Optional[KnowledgeEngine] = None
        self.internet_engine: Optional[InternetEngine] = None
        self.llm_provider: Optional[BaseLLMProvider] = None
        self.llm_engine: Optional[LLMEngine] = None

        # Vision
        self.screen_capture: Optional[ScreenCapture] = None
        self.screen_reader: Optional[ScreenReader] = None
        self.screen_analyzer: Optional[ScreenAnalyzer] = None

        # Voice
        self.voice_controller: Optional[VoiceController] = None

        # Desktop
        self.application_launcher: Optional[ApplicationLauncher] = None
        self.window_manager: Optional[WindowManager] = None
        self.mouse_controller: Optional[MouseController] = None
        self.keyboard_controller: Optional[KeyboardController] = None
        self.clipboard_manager: Optional[ClipboardManager] = None
        self.desktop_controller: Optional[DesktopController] = None

        # Execution
        self.execution_executor: Optional[ExecutionStepExecutor] = None
        self.execution_engine: Optional[ExecutionEngine] = None

        # Planning and Routing
        self.planner_engine: Optional[PlannerEngine] = None
        self.router: Optional[Router] = None
        self.brain: Optional[EchoBrain] = None

        # Context
        self.context_engine = get_context_engine()

        # Initialize all subsystems
        self._initialize_subsystems()
        self._initialized = True

    def _setup_logging(self) -> logging.Logger:
        """Setup and return a configured logger."""
        logger = logging.getLogger("echodesk")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def _initialize_subsystems(self) -> None:
        """Initialize all EchoDesk subsystems."""
        try:
            # Memory subsystem
            self._initialize_memory()
            
            # Knowledge, internet, and LLM
            self._initialize_knowledge()
            self._initialize_internet()
            self._initialize_llm()
            
            # Vision subsystem
            self._initialize_vision()
            
            # Voice subsystem
            self._initialize_voice()
            
            # Desktop subsystem
            self._initialize_desktop()
            
            # Execution subsystem
            self._initialize_execution()
            
            # Planning and Routing
            self._initialize_planning()
            
            # Brain (central processor)
            self._initialize_brain()
            
            self.logger.info("All subsystems initialized successfully.")
        except Exception as e:
            self.logger.error(f"Failed to initialize subsystems: {e}")
            raise

    def _initialize_memory(self) -> None:
        """Initialize memory subsystems."""
        try:
            self.memory_storage = MemoryStorage()
            self.memory_manager = MemoryManager(self.memory_storage)
            memory_retrieval = MemoryRetrieval(self.memory_manager)
            memory_search = MemorySearch(memory_retrieval)
            self.memory_controller = MemoryController(
                manager=self.memory_manager,
                retrieval=memory_retrieval,
                search_service=memory_search,
            )
            self.logger.info("Memory subsystem initialized.")
        except Exception as e:
            self.logger.warning(f"Memory subsystem initialization failed: {e}")

    def _initialize_knowledge(self) -> None:
        """Initialize knowledge engine."""
        try:
            self.knowledge_engine = KnowledgeEngine()
            self.logger.info("Knowledge engine initialized.")
        except Exception as e:
            self.logger.warning(f"Knowledge engine initialization failed: {e}")

    def _initialize_internet(self) -> None:
        """Initialize internet search engine."""
        try:
            self.internet_engine = InternetEngine()
            self.logger.info("Internet engine initialized.")
        except Exception as e:
            self.logger.warning(f"Internet engine initialization failed: {e}")

    def _initialize_llm(self) -> None:
        """Initialize LLM provider and engine."""
        try:
            # Try to use Ollama provider
            self.llm_provider = OllamaProvider()
            self.llm_engine = LLMEngine(self.llm_provider)
            self.logger.info("LLM engine initialized with Ollama provider.")
        except Exception as e:
            self.logger.warning(f"LLM engine initialization failed: {e}")
            self.llm_provider = None
            self.llm_engine = None

    def _initialize_vision(self) -> None:
        """Initialize vision subsystems (screen capture, reading, analysis)."""
        try:
            self.screen_capture = ScreenCapture()
            self.screen_reader = ScreenReader()
            self.screen_analyzer = ScreenAnalyzer()
            self.logger.info("Vision subsystem initialized.")
        except Exception as e:
            self.logger.warning(f"Vision subsystem initialization failed: {e}")

    def _initialize_voice(self) -> None:
        """Initialize voice subsystems (speech recognition/synthesis)."""
        try:
            self.voice_controller = VoiceController()
            self.logger.info("Voice controller initialized.")
        except Exception as e:
            self.logger.warning(f"Voice controller initialization failed: {e}")

    def _initialize_desktop(self) -> None:
        """Initialize desktop automation subsystems."""
        try:
            self.application_launcher = ApplicationLauncher()
            self.window_manager = WindowManager()
            self.mouse_controller = MouseController()
            self.keyboard_controller = KeyboardController()
            self.clipboard_manager = ClipboardManager()
            
            self.desktop_controller = DesktopController(
                launcher=self.application_launcher,
                mouse_controller=self.mouse_controller,
                keyboard_controller=self.keyboard_controller,
                window_manager=self.window_manager,
                clipboard_manager=self.clipboard_manager,
            )
            self.logger.info("Desktop controller initialized.")
        except Exception as e:
            self.logger.warning(f"Desktop controller initialization failed: {e}")

    def _initialize_execution(self) -> None:
        """Initialize task execution subsystems."""
        try:
            # Build tool registry
            tool_registry = {}
            if self.desktop_controller:
                tool_registry["DesktopController"] = self.desktop_controller
            if self.screen_capture:
                tool_registry["ScreenCapture"] = self.screen_capture
            if self.screen_reader:
                tool_registry["ScreenReader"] = self.screen_reader
            if self.screen_analyzer:
                tool_registry["ScreenAnalyzer"] = self.screen_analyzer
            if self.memory_manager:
                tool_registry["MemoryManager"] = self.memory_manager
            if self.knowledge_engine:
                tool_registry["KnowledgeEngine"] = self.knowledge_engine
            
            self.execution_executor = ExecutionStepExecutor(tool_registry)
            self.execution_engine = ExecutionEngine(step_executor=self.execution_executor)
            self.logger.info("Execution engines initialized.")
        except Exception as e:
            self.logger.warning(f"Execution engine initialization failed: {e}")

    def _initialize_planning(self) -> None:
        """Initialize planning and routing subsystems."""
        try:
            self.planner_engine = PlannerEngine()
            self.router = Router()
            self.logger.info("Planning and routing initialized.")
        except Exception as e:
            self.logger.warning(f"Planning initialization failed: {e}")

    def _initialize_brain(self) -> None:
        """Initialize the brain (central processor)."""
        try:
            self.brain = EchoBrain(
                memory_controller=self.memory_controller,
                knowledge_engine=self.knowledge_engine,
                internet_engine=self.internet_engine,
                llm_engine=self.llm_engine,
                desktop_controller=self.desktop_controller,
                context_engine=self.context_engine,
            )
            self.logger.info("Brain initialized.")
        except Exception as e:
            self.logger.warning(f"Brain initialization failed: {e}")

    def validate_dependencies(self) -> Dict[str, bool]:
        """
        Validate that required dependencies are available.

        Returns:
            Dictionary mapping subsystem names to availability status.
        """
        status = {
            "memory": self.memory_manager is not None,
            "knowledge": self.knowledge_engine is not None,
            "internet": self.internet_engine is not None,
            "llm": self.llm_engine is not None,
            "vision": self.screen_capture is not None,
            "voice": self.voice_controller is not None,
            "desktop": self.desktop_controller is not None,
            "execution": self.execution_executor is not None,
            "planning": self.planner_engine is not None,
            "brain": self.brain is not None,
        }
        return status

    def start(self) -> None:
        """Start EchoDesk runtime."""
        with self._lock:
            if self._running:
                self.logger.warning("EchoDesk is already running.")
                return
            
            if not self._initialized:
                self.logger.error("EchoDesk not properly initialized.")
                return
            
            self._running = True
            self.logger.info("EchoDesk runtime started.")

    def shutdown(self) -> None:
        """Gracefully shut down EchoDesk."""
        with self._lock:
            if not self._running:
                return
            
            self._running = False
            self.logger.info("EchoDesk runtime shutdown.")

    def process(self, text: str) -> Dict[str, Any]:
        """
        Process a text command through the routing system.

        Args:
            text: The user's input command.

        Returns:
            Response dictionary with processing results.
        """
        if not self._running:
            return {
                "success": False,
                "message": "EchoDesk is not running."
            }
        
        try:
            if not text or not text.strip():
                return {
                    "success": False,
                    "message": "Empty command received."
                }
            
            # Route the command
            if self.router:
                route = self.router.route(text)
                
                # Process based on route
                if isinstance(route, dict) and route.get("route") == "execute_plan":
                    plan = route.get("plan")
                    if self.execution_engine and plan:
                        return self.execution_engine.execute_plan(plan)
                    return {
                        "success": False,
                        "message": "Execution engine not available."
                    }
                
                # If brain can handle it
                if self.brain:
                    result = self.brain.process(text)
                    return {
                        "success": True,
                        "message": result,
                        "route": route
                    }
            
            return {
                "success": True,
                "message": "Command processed.",
                "input": text
            }
        except Exception as e:
            self.logger.error(f"Error processing command: {e}")
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }

    def process_voice(self) -> Dict[str, Any]:
        """
        Process voice input through speech recognition.

        Returns:
            Response dictionary with recognized text or error.
        """
        if not self.voice_controller:
            return {
                "success": False,
                "message": "Voice controller not available."
            }
        
        try:
            result = self.voice_controller.listen_command()
            if result.get("success"):
                text = result.get("result", {}).get("text", "")
                return self.process(text)
            return result
        except Exception as e:
            self.logger.error(f"Voice processing error: {e}")
            return {
                "success": False,
                "message": f"Voice processing failed: {str(e)}"
            }

    def capture_screen(self) -> Dict[str, Any]:
        """
        Capture a screenshot.

        Returns:
            Response dictionary with screenshot path or error.
        """
        if not self.screen_capture:
            return {
                "success": False,
                "message": "Screen capture not available."
            }
        
        try:
            path = self.screen_capture.take_screenshot()
            return {
                "success": True,
                "message": "Screenshot captured.",
                "result": path
            }
        except Exception as e:
            self.logger.error(f"Screenshot error: {e}")
            return {
                "success": False,
                "message": f"Screenshot failed: {str(e)}"
            }

    def read_screen(self) -> Dict[str, Any]:
        """
        Capture and read text from the screen.

        Returns:
            Response dictionary with screen text or error.
        """
        if not self.screen_capture or not self.screen_reader:
            return {
                "success": False,
                "message": "Screen reading not available."
            }
        
        try:
            screenshot_path = self.screen_capture.take_screenshot()
            text = self.screen_reader.read_image(screenshot_path)
            return {
                "success": True,
                "message": "Screen read successfully.",
                "result": text
            }
        except Exception as e:
            self.logger.error(f"Screen reading error: {e}")
            return {
                "success": False,
                "message": f"Screen reading failed: {str(e)}"
            }

    def remember(self, text: str, category: str = "general") -> Dict[str, Any]:
        """
        Store information in memory.

        Args:
            text: The text to remember.
            category: Memory category for organization.

        Returns:
            Response dictionary indicating success or failure.
        """
        if not self.memory_manager:
            return {
                "success": False,
                "message": "Memory system not available."
            }
        
        try:
            # Extract key-value from text or use default
            parts = text.split(":", 1)
            if len(parts) == 2:
                key, value = parts[0].strip(), parts[1].strip()
            else:
                key = f"memory_{len(parts)}"
                value = text
            
            return self.memory_manager.remember(key, value, category)
        except Exception as e:
            self.logger.error(f"Memory error: {e}")
            return {
                "success": False,
                "message": f"Memory operation failed: {str(e)}"
            }

    def recall(self, query: str) -> Dict[str, Any]:
        """
        Retrieve information from memory.

        Args:
            query: The memory key or query to search for.

        Returns:
            Response dictionary with recalled information or error.
        """
        if not self.memory_manager:
            return {
                "success": False,
                "message": "Memory system not available."
            }
        
        try:
            return self.memory_manager.recall(query.strip())
        except Exception as e:
            self.logger.error(f"Recall error: {e}")
            return {
                "success": False,
                "message": f"Recall operation failed: {str(e)}"
            }

    def launch(self, app_name: str) -> Dict[str, Any]:
        """
        Launch an application.

        Args:
            app_name: Name of the application to launch.

        Returns:
            Response dictionary indicating success or failure.
        """
        if not self.application_launcher:
            return {
                "success": False,
                "message": "Application launcher not available."
            }
        
        try:
            return self.application_launcher.launch(app_name)
        except Exception as e:
            self.logger.error(f"Launch error: {e}")
            return {
                "success": False,
                "message": f"Launch failed: {str(e)}"
            }

    def execute(self, task_description: str) -> Dict[str, Any]:
        """
        Execute a task description through the planning engine.

        Args:
            task_description: Description of the task to execute.

        Returns:
            Response dictionary with execution results.
        """
        if not self.planner_engine or not self.execution_engine:
            return {
                "success": False,
                "message": "Execution system not available."
            }
        
        try:
            # Create a plan from the task description
            plan = self.planner_engine.plan(task_description)
            if not plan or not plan.get("success"):
                return {
                    "success": False,
                    "message": "Failed to create execution plan."
                }
            
            # Execute the plan
            return self.execution_engine.execute_plan(plan.get("result"))
        except Exception as e:
            self.logger.error(f"Execution error: {e}")
            return {
                "success": False,
                "message": f"Execution failed: {str(e)}"
            }

    def status(self) -> Dict[str, Any]:
        """
        Get the current status of EchoDesk and all subsystems.

        Returns:
            Dictionary containing status information for all subsystems.
        """
        dependencies = self.validate_dependencies()
        
        return {
            "running": self._running,
            "initialized": self._initialized,
            "subsystems": dependencies,
            "subsystems_active": sum(1 for v in dependencies.values() if v),
            "subsystems_total": len(dependencies),
        }
