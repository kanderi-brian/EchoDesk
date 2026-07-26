"""Startup and support UI helpers; they do not own EchoBrain behavior."""
from __future__ import annotations

import platform
import sys
import traceback
from typing import Any

from core.app_paths import resource_path
from core.logging_config import category_logger


APP_VERSION = "3.2.0"
BUILD_NUMBER = "320"


def ollama_status() -> str:
    try:
        from llm.ollama_provider import OllamaProvider
        return "Connected" if OllamaProvider().is_running() else "Unavailable"
    except Exception:
        return "Unavailable"


def install_crash_handler(parent: Any = None) -> None:
    """Record unexpected GUI exceptions and present a recoverable message."""
    def handle(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback); return
        category_logger("errors").error("Unhandled exception\n%s", "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
        try:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(parent, "EchoDesk encountered a problem", "EchoDesk encountered an unexpected problem. Details were saved to the errors log. You can restart the application safely.")
        except Exception:
            pass
    sys.excepthook = handle


def show_about(parent: Any = None) -> None:
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QMessageBox
    icon = resource_path("assets/echodesk.svg")
    dialog = QMessageBox(parent); dialog.setWindowTitle("About EchoDesk")
    dialog.setIconPixmap(QIcon(str(icon)).pixmap(64, 64))
    dialog.setText("EchoDesk Desktop Assistant")
    dialog.setInformativeText(
        f"Version {APP_VERSION} (build {BUILD_NUMBER})\n"
        f"Python {platform.python_version()}\nOllama: {ollama_status()}\n"
        f"{platform.system()} {platform.release()}\n\n"
        "Local AI Desktop Assistant\nLicense: See LICENSE bundled with EchoDesk."
    )
    dialog.exec()
