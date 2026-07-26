"""EchoDesk desktop entrypoint: floating assistant first, console fallback."""
from __future__ import annotations
import argparse
import importlib.util

from core.app_paths import ensure_data_directories
from core.logging_config import category_logger, setup_logging
from ui.application_support import install_crash_handler, ollama_status


def studio_available() -> bool:
    """Return whether the optional PySide6 Studio dependency is installed."""
    return importlib.util.find_spec("PySide6") is not None


def startup_diagnostics() -> dict[str, str]:
    """Lightweight diagnostics suitable for startup messages and support logs."""
    checks = {"studio": "available" if studio_available() else "PySide6 is not installed; console mode will be used"}
    try:
        from llm.ollama_provider import OllamaProvider
        checks["llm"] = f"{ollama_status()} ({OllamaProvider().model})"
    except Exception as exc: checks["llm"] = f"unavailable: {exc}"
    for name, module in (("voice", "voice.voice_engine"), ("vision", "vision.vision_engine")):
        checks[name] = "available" if importlib.util.find_spec(module) else "dependency unavailable"
    try:
        from plugins.plugin_manager import PluginManager
        checks["plugins"] = f"{len(PluginManager().discover())} discovered"
    except Exception as exc: checks["plugins"] = f"unavailable: {exc}"
    checks["memory"] = "available"
    return checks


def console_main() -> None:
    """Minimal interactive console fallback; unlike the old demo it performs no test queries."""
    from brain.brain import EchoBrain
    brain = EchoBrain()
    print("EchoDesk console mode. Type 'exit' to quit.")
    while True:
        try: command = input("You> ").strip()
        except (EOFError, KeyboardInterrupt): break
        if command.lower() in {"exit", "quit"}: break
        if command: print(f"EchoDesk> {brain.process(command)}")


def run_desktop(brain) -> int:
    """Launch the hidden-at-startup desktop host without changing Brain internals."""
    from desktop.runtime import run_background_desktop
    return run_background_desktop(brain)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="EchoDesk desktop assistant")
    parser.add_argument("--console", action="store_true", help="run the console interface even when Studio is available")
    parser.add_argument("--background", action="store_true", help="internal: start hidden for Windows sign-in")
    args = parser.parse_args(argv)
    ensure_data_directories(); setup_logging(); install_crash_handler()
    diagnostics = startup_diagnostics()
    category_logger("startup").info("Startup diagnostics: %s", diagnostics)
    instance = None
    if not args.console and studio_available():
        from desktop.single_instance import SingleInstance
        instance = SingleInstance()
        if not instance.acquire():
            category_logger("startup").info("EchoDesk is already running")
            return
        from brain.brain import EchoBrain
        if diagnostics["llm"].startswith("Unavailable"):
            category_logger("startup").warning("Ollama is unavailable; starting with friendly fallback messaging.")
        brain = EchoBrain()
        if diagnostics["llm"].startswith("Unavailable"):
            brain.startup_notice = "Ollama is unavailable. Start Ollama to enable local AI responses."
        try:
            run_desktop(brain)
        finally:
            instance.release()
        return
    print("Studio unavailable or console requested: " + diagnostics["studio"])
    console_main()


if __name__ == "__main__": main()
