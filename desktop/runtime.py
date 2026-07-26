"""Background desktop host that composes the existing Brain, Studio and VoiceEngine."""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Callable

from core.config import get_config, save_config
from desktop.startup import StartupManager
from voice.voice_engine import VoiceConfig, VoiceEngine


class VoiceWakeService:
    """Own microphone ownership in one recoverable worker, avoiding UI blocking."""
    def __init__(self, voice: VoiceEngine, awakened: Callable[[str], None], logger: logging.Logger | None = None) -> None:
        self.voice, self.awakened = voice, awakened
        self.logger = logger or logging.getLogger("echodesk.voice_wake")
        self._stop = threading.Event(); self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and not self._stop.is_set())

    def start(self) -> None:
        if self.running: return
        self._stop.clear(); self.voice.start()
        self._thread = threading.Thread(target=self._run, name="EchoDeskVoiceWake", daemon=True); self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                result = self.voice.listen()
                if result.get("success") and result.get("wake_word_detected"):
                    self.awakened(str(result.get("transcript", "")))
                elif not result.get("success"):
                    # Recognition backends can fail transiently. Back off before reclaiming the mic.
                    self.logger.debug("Voice recognition retry: %s", result.get("message"))
                    self._stop.wait(0.35)
            except Exception:
                self.logger.exception("Voice wake worker failed; retrying")
                self._stop.wait(1.0)

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set(); self.voice.stop()
        if self._thread and self._thread is not threading.current_thread(): self._thread.join(timeout)


class GlobalHotkeyService:
    """Small Win32 global-hotkey listener; unavailable platforms remain no-ops."""
    def __init__(self, hotkey: str, activated: Callable[[], None], logger: logging.Logger | None = None) -> None:
        self.hotkey, self.activated = hotkey, activated
        self.logger = logger or logging.getLogger("echodesk.hotkey")
        self._thread: threading.Thread | None = None; self._thread_id: int | None = None
        self._stop = threading.Event(); self._registered = False

    @staticmethod
    def _keys(spec: str) -> tuple[int, int]:
        parts = [part.strip().lower() for part in spec.split("+")]
        modifiers = (2 if "ctrl" in parts or "control" in parts else 0) | (4 if "shift" in parts else 0) | (1 if "alt" in parts else 0)
        key = next((part for part in reversed(parts) if part not in {"ctrl", "control", "shift", "alt"}), "space")
        if key == "space": return modifiers, 0x20
        if len(key) == 1 and key.isalnum(): return modifiers, ord(key.upper())
        raise ValueError(f"Unsupported global hotkey: {spec}")

    def start(self) -> None:
        if os.name != "nt" or self._thread and self._thread.is_alive(): return
        self._stop.clear(); self._thread = threading.Thread(target=self._run, name="EchoDeskHotkey", daemon=True); self._thread.start()

    def _run(self) -> None:
        try:
            import ctypes
            from ctypes import wintypes
            modifiers, key = self._keys(self.hotkey); user32 = ctypes.windll.user32; kernel32 = ctypes.windll.kernel32
            self._thread_id = kernel32.GetCurrentThreadId()
            self._registered = bool(user32.RegisterHotKey(None, 0xEC01, modifiers, key))
            if not self._registered:
                self.logger.warning("Global hotkey is unavailable: %s", self.hotkey); return
            message = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                if message.message == 0x0312: self.activated()
        except Exception:
            self.logger.exception("Global hotkey failed")
        finally:
            try:
                if self._registered: ctypes.windll.user32.UnregisterHotKey(None, 0xEC01)
            except Exception: pass
            self._registered = False

    def stop(self, timeout: float = 1.0) -> None:
        self._stop.set()
        if os.name == "nt" and self._thread_id:
            try:
                import ctypes
                ctypes.windll.user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)
            except Exception: pass
        if self._thread and self._thread is not threading.current_thread(): self._thread.join(timeout)


def _qt_runtime():
    """Keep Qt imports lazy so runtime services remain unit-testable without PySide."""
    from PySide6.QtCore import QObject, Signal
    from PySide6.QtGui import QAction, QKeySequence
    from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon
    return QObject, Signal, QAction, QKeySequence, QApplication, QMenu, QStyle, QSystemTrayIcon


def run_background_desktop(brain: Any) -> int:
    """Run hidden at sign-in; expose the existing Studio chat window on wake."""
    QObject, Signal, QAction, QKeySequence, QApplication, QMenu, QStyle, QSystemTrayIcon = _qt_runtime()
    from ui.studio import StudioMainWindow

    class Bridge(QObject):
        awakened = Signal(str)

    app = QApplication.instance() or QApplication([]); app.setQuitOnLastWindowClosed(False)
    window = StudioMainWindow(brain=brain)
    window.setWindowTitle("EchoDesk")
    bridge = Bridge()

    def show_chat(transcript: str = "") -> None:
        window.showNormal(); window.raise_(); window.activateWindow()
        window.navigation.setCurrentRow(0); window.chat.input.setFocus()
        if transcript:
            window.chat.input.setPlainText(transcript)

    bridge.awakened.connect(show_chat)
    cfg = get_config().get("desktop", {})
    voice = getattr(getattr(brain, "executor", None), "_voice_engine", None)
    if voice is None:
        voice = VoiceEngine(VoiceConfig(wake_word=str(cfg.get("wake_word", "Hey Echo"))))
        brain.executor._voice_engine = voice
    wake = VoiceWakeService(voice, bridge.awakened.emit)
    global_hotkey = GlobalHotkeyService(str(cfg.get("hotkey", "Ctrl+Shift+Space")), lambda: bridge.awakened.emit(""))

    tray = QSystemTrayIcon(window.style().standardIcon(QStyle.SP_ComputerIcon), window)
    tray.setToolTip("EchoDesk")
    menu = QMenu(window)
    open_action = QAction("Open EchoDesk", window); open_action.triggered.connect(show_chat)
    start_action = QAction("Start Listening", window); start_action.triggered.connect(wake.start)
    stop_action = QAction("Stop Listening", window); stop_action.triggered.connect(wake.stop)
    settings_action = QAction("Settings", window); settings_action.triggered.connect(lambda: (show_chat(), window.navigation.setCurrentRow(window.navigation.count() - 1)))
    exit_action = QAction("Exit", window)
    menu.addActions([open_action, start_action, stop_action, settings_action]); menu.addSeparator(); menu.addAction(exit_action)
    tray.setContextMenu(menu); tray.activated.connect(lambda reason: show_chat() if reason == QSystemTrayIcon.Trigger else None); tray.show()

    shortcut = QKeySequence(str(cfg.get("hotkey", "Ctrl+Shift+Space")))
    # This is also useful while running from source on non-Windows platforms.
    hotkey_action = QAction(window); hotkey_action.setShortcut(shortcut); hotkey_action.setShortcutContext(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.ApplicationShortcut); hotkey_action.triggered.connect(show_chat); window.addAction(hotkey_action)

    def shutdown() -> None:
        global_hotkey.stop(); wake.stop(); tray.hide(); window.save_session()
        try:
            brain.stop_runtime(); brain.shutdown_plugins()
            project_agent = getattr(brain, "project_agent", None)
            if project_agent is not None: project_agent.stop()
        except Exception: logging.getLogger("echodesk.desktop").exception("Background shutdown failed")
    app.aboutToQuit.connect(shutdown)
    exit_action.triggered.connect(app.quit)
    global_hotkey.start()
    if cfg.get("listen_on_startup", True): wake.start()
    # Never display the main window until tray, hotkey, or wake word activation.
    return app.exec()
