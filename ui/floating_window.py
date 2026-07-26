"""Small, production-facing desktop shell for EchoDesk.

This module only presents existing EchoBrain and VoiceEngine capabilities.  It
does not own planning, reasoning, or automation behavior.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import (Property, QAbstractAnimation, QEvent, QPoint, QPropertyAnimation,
    QThread, QTimer, Qt, Signal)
from PySide6.QtGui import QAction, QColor, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QMenu,
    QStyle, QSystemTrayIcon, QVBoxLayout, QWidget)
from .application_support import show_about


VOICE_STATES = ("Idle", "Listening", "Thinking", "Speaking")


class MicrophoneIndicator(QWidget):
    """Painted microphone with a non-blocking glow animation."""
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = "Idle"
        self._glow = 0.25
        self.setFixedSize(44, 44)
        self.animation = QPropertyAnimation(self, b"glow", self)
        self.animation.setStartValue(0.2); self.animation.setEndValue(1.0)
        self.animation.setDuration(850); self.animation.setLoopCount(-1)

    def get_glow(self) -> float:
        return self._glow

    def set_glow(self, value: float) -> None:
        self._glow = float(value); self.update()

    glow = Property(float, get_glow, set_glow)

    def set_state(self, state: str) -> None:
        self.state = state if state in VOICE_STATES else "Idle"
        if self.state == "Idle":
            self.animation.stop(); self.set_glow(0.25)
        else:
            self.animation.setDuration(500 if self.state == "Listening" else 850)
            if self.animation.state() != QAbstractAnimation.Running: self.animation.start()
        self.setAccessibleName(f"Voice status: {self.state}")

    def paintEvent(self, event: QEvent) -> None:  # noqa: N802 - Qt callback
        colors = {"Idle": "#8b95a7", "Listening": "#4dd6ff", "Thinking": "#9c7cff", "Speaking": "#55df9b"}
        color = QColor(colors[self.state]); painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
        color.setAlphaF(0.16 + self._glow * 0.3); painter.setBrush(color); painter.setPen(Qt.NoPen)
        painter.drawEllipse(2, 2, 40, 40)
        color.setAlpha(255); painter.setPen(QPen(color, 3)); painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(17, 10, 10, 17, 5, 5); painter.drawArc(12, 16, 20, 20, 0, -180 * 16)
        painter.drawLine(22, 36, 22, 40); painter.drawLine(16, 40, 28, 40)


class VoiceStatusBridge(QWidget):
    """Adapts the existing VoiceEngine session state to one display state."""
    state_changed = Signal(str)

    def __init__(self, voice_engine: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent); self.voice_engine = voice_engine; self.thinking = False; self.state = "Idle"
        self.timer = QTimer(self); self.timer.timeout.connect(self.refresh); self.timer.start(150); self.refresh()

    def set_thinking(self, active: bool) -> None:
        self.thinking = active; self.refresh()

    def refresh(self) -> None:
        try: status = self.voice_engine.status()
        except Exception: status = {}
        state = "Speaking" if status.get("speaking") else "Listening" if status.get("listening") else "Thinking" if self.thinking else "Idle"
        if state != self.state: self.state = state; self.state_changed.emit(state)


class VoiceCommandWorker(QThread):
    """Runs microphone capture and existing EchoBrain processing away from Qt."""
    completed = Signal(str)
    failed = Signal(str)
    thinking_started = Signal()

    def __init__(self, voice_engine: Any, brain: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent); self.voice_engine = voice_engine; self.brain = brain

    def run(self) -> None:
        try:
            result = self.voice_engine.listen()
            if not result.get("success"): self.failed.emit(result.get("message", "Voice input failed.")); return
            transcript = result.get("transcript", "").strip()
            if not transcript: self.completed.emit(result.get("message", "Listening complete.")); return
            self.thinking_started.emit()
            self.completed.emit(str(self.brain.process(transcript)))
        except Exception as exc:
            self.failed.emit(f"Voice unavailable: {exc}")


class FloatingAssistantWindow(QWidget):
    """Top-centre, always-on-top assistant window with tray controls."""
    def __init__(self, brain: Any, voice_engine: Any | None = None) -> None:
        super().__init__(); self.brain = brain; self._exiting = False; self._drag_origin: QPoint | None = None
        self.voice_engine = voice_engine or self._voice_engine_for(brain)
        self.setWindowTitle("EchoDesk")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground); self.setFixedSize(356, 82)
        self._build_ui(); self._build_tray(); self._position_top_center()

    @staticmethod
    def _voice_engine_for(brain: Any) -> Any:
        executor = brain.executor; engine = getattr(executor, "_voice_engine", None)
        if engine is None:
            from voice.voice_engine import VoiceEngine
            engine = VoiceEngine(); executor._voice_engine = engine
        return engine

    def _build_ui(self) -> None:
        card = QWidget(self); card.setObjectName("assistantCard")
        layout = QHBoxLayout(card); layout.setContentsMargins(18, 13, 18, 13); layout.setSpacing(12)
        self.microphone = MicrophoneIndicator(); self.status_label = QLabel("Idle"); self.status_label.setObjectName("voiceStatus")
        self.status_label.setAccessibleName("Current voice status")
        notice = getattr(self.brain, "startup_notice", "EchoDesk is ready")
        hint = QLabel(notice if isinstance(notice, str) else "EchoDesk is ready"); hint.setObjectName("statusHint")
        text = QVBoxLayout(); text.setSpacing(1); text.addWidget(self.status_label); text.addWidget(hint)
        layout.addWidget(self.microphone); layout.addLayout(text); layout.addStretch()
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.addWidget(card)
        self.setStyleSheet("""
            #assistantCard { background: rgba(18, 24, 38, 235); border: 1px solid rgba(130, 151, 184, 105); border-radius: 22px; }
            #voiceStatus { color: #f4f7ff; font-size: 16px; font-weight: 600; }
            #statusHint { color: #aebbd0; font-size: 11px; }
        """)
        self.status_bridge = VoiceStatusBridge(self.voice_engine, self); self.status_bridge.state_changed.connect(self._set_status)
        self.microphone.set_state(self.status_bridge.state)

    def _build_tray(self) -> None:
        icon = self.style().standardIcon(QStyle.SP_MediaPlay)
        self.tray = QSystemTrayIcon(icon, self); self.tray.setToolTip("EchoDesk")
        menu = QMenu(self); self.show_action = QAction("Show EchoDesk", self); self.hide_action = QAction("Hide EchoDesk", self); self.exit_action = QAction("Exit EchoDesk", self)
        self.show_action.triggered.connect(self.show_assistant); self.hide_action.triggered.connect(self.hide); self.exit_action.triggered.connect(self.exit_application)
        self.about_action = QAction("About EchoDesk", self); self.about_action.triggered.connect(lambda: show_about(self))
        menu.addAction(self.show_action); menu.addAction(self.hide_action); menu.addAction(self.about_action); menu.addSeparator(); menu.addAction(self.exit_action)
        self.tray.setContextMenu(menu); self.tray.activated.connect(self._tray_activated); self.tray.show()

    def _set_status(self, state: str) -> None:
        self.status_label.setText(state); self.microphone.set_state(state)

    def _position_top_center(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None: return
        area = screen.availableGeometry(); self.move(area.center().x() - self.width() // 2, area.top() + 24)

    def show_assistant(self) -> None:
        self._position_top_center(); self.show(); self.raise_(); self.activateWindow()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self.show_assistant() if self.isHidden() else self.hide()

    def start_voice_capture(self) -> None:
        if hasattr(self, "worker") and self.worker.isRunning(): return
        self.worker = VoiceCommandWorker(self.voice_engine, self.brain, self); self.status_bridge.set_thinking(False)
        self.worker.thinking_started.connect(lambda: self.status_bridge.set_thinking(True))
        self.worker.completed.connect(self._voice_completed); self.worker.failed.connect(self._voice_failed); self.worker.start()

    def _voice_completed(self, message: str) -> None:
        self.status_bridge.set_thinking(False); self.tray.showMessage("EchoDesk", message[:160], QSystemTrayIcon.Information, 3500)

    def _voice_failed(self, message: str) -> None:
        self.status_bridge.set_thinking(False); self.tray.showMessage("EchoDesk", message[:160], QSystemTrayIcon.Warning, 3500)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt callback
        if event.button() == Qt.LeftButton: self._drag_origin = event.globalPosition().toPoint() - self.frameGeometry().topLeft(); self.start_voice_capture()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt callback
        if self._drag_origin is not None and event.buttons() & Qt.LeftButton: self.move(event.globalPosition().toPoint() - self._drag_origin)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt callback
        self._drag_origin = None

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt callback
        if self._exiting: event.accept(); return
        event.ignore(); self.hide()

    def exit_application(self) -> None:
        self._exiting = True; self.status_bridge.timer.stop(); self.tray.hide()
        try: self.voice_engine.stop()
        except Exception: pass
        self.close(); QApplication.quit()


def run_desktop(brain: Any) -> int:
    """Create the production shell using the already-initialized EchoBrain."""
    app = QApplication.instance() or QApplication([]); app.setQuitOnLastWindowClosed(False)
    window = FloatingAssistantWindow(brain); window.show_assistant(); return app.exec()
