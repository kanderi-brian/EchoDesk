"""EchoDesk Studio, an additive PySide6 control centre for EchoBrain."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QCheckBox, QDockWidget, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMainWindow,
    QMessageBox, QPlainTextEdit, QPushButton, QProgressBar, QSplitter,
    QStackedWidget, QStatusBar, QTableWidget, QTableWidgetItem, QToolBar,
    QVBoxLayout, QWidget)

from brain.brain import EchoBrain
from core.config import get_config, save_config


class SessionStore:
    """Small, explicit UI-only session store; it never stores credentials."""
    def __init__(self, path: str = "studio_session.json") -> None:
        self.path = Path(path)

    def load(self) -> dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def save(self, state: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(state, indent=2), encoding="utf-8")


class ChatWorkspace(QWidget):
    """Accessible rich-text chat surface using the existing EchoBrain.process API."""
    attachment_added = Signal(str)

    def __init__(self, brain: EchoBrain, parent: QWidget | None = None) -> None:
        super().__init__(parent); self.brain = brain; self.attachments: list[str] = []
        self.setAcceptDrops(True); layout = QVBoxLayout(self)
        self.transcript = QPlainTextEdit(readOnly=True); self.transcript.setAccessibleName("Conversation history")
        self.input = QPlainTextEdit(); self.input.setPlaceholderText("Ask EchoDesk… (Ctrl+Enter to send)"); self.input.setFixedHeight(72)
        row = QHBoxLayout(); self.send = QPushButton("Send"); self.attach = QPushButton("Attach file")
        self.send.clicked.connect(self.send_message); self.attach.clicked.connect(self.add_attachment)
        row.addWidget(self.attach); row.addStretch(); row.addWidget(self.send)
        layout.addWidget(self.transcript); layout.addWidget(self.input); layout.addLayout(row)

    def send_message(self) -> None:
        text = self.input.toPlainText().strip()
        if not text: return
        self.transcript.appendPlainText(f"You: {text}")
        self.input.clear()
        try: response = self.brain.process(text)
        except Exception as exc: response = f"Error: {exc}"
        self.transcript.appendPlainText(f"EchoDesk: {response}\n")

    def add_attachment(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Attach file")
        if path: self.attach_file(path)

    def attach_file(self, path: str) -> None:
        if path not in self.attachments:
            self.attachments.append(path); self.attachment_added.emit(path)
            self.transcript.appendPlainText(f"Attached: {Path(path).name}")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if url.isLocalFile(): self.attach_file(url.toLocalFile())
        event.acceptProposedAction()


class Dashboard(QWidget):
    """Generic dashboard table populated by a safe summary provider."""
    def __init__(self, title: str, provider, parent: QWidget | None = None) -> None:
        super().__init__(parent); self.provider = provider
        layout = QVBoxLayout(self); layout.addWidget(QLabel(title))
        self.table = QTableWidget(0, 2); self.table.setHorizontalHeaderLabels(["Metric", "Value"])
        self.table.setAccessibleName(title); layout.addWidget(self.table)

    def refresh(self) -> None:
        try: data = self.provider() or {}
        except Exception as exc: data = {"status": f"Unavailable: {exc}"}
        rows = self._flatten(data)
        self.table.setRowCount(len(rows))
        for index, (key, value) in enumerate(rows):
            self.table.setItem(index, 0, QTableWidgetItem(key))
            self.table.setItem(index, 1, QTableWidgetItem(value))

    @staticmethod
    def _flatten(data: Any, prefix: str = "") -> list[tuple[str, str]]:
        if isinstance(data, dict):
            rows = []
            for key, value in data.items(): rows.extend(Dashboard._flatten(value, f"{prefix}.{key}".strip(".")))
            return rows
        if isinstance(data, list): return [(prefix, f"{len(data)} item(s)")]
        return [(prefix or "value", str(data))]


class StudioMainWindow(QMainWindow):
    """Dockable Studio shell. All commands delegate to existing service APIs."""
    def __init__(self, brain: EchoBrain | None = None, session_path: str = "studio_session.json") -> None:
        super().__init__(); self.brain = brain or EchoBrain(); self.sessions = SessionStore(session_path)
        self.setWindowTitle("EchoDesk Studio"); self.resize(1360, 820); self.setDockNestingEnabled(True)
        self._build_shell(); self._restore_session()
        self.refresh_timer = QTimer(self); self.refresh_timer.timeout.connect(self.refresh_dashboards); self.refresh_timer.start(2000)

    def _build_shell(self) -> None:
        self._build_menu(); self._build_toolbar(); self.statusBar().showMessage("Studio ready")
        self.navigation = QListWidget(); self.navigation.setAccessibleName("Studio navigation")
        self.pages = QStackedWidget(); self.chat = ChatWorkspace(self.brain)
        providers = {
            "Projects": lambda: {"goals": self.brain.list_goals(), "progress": self.brain.get_progress()},
            "Agents": self.brain.get_agent_metrics,
            "Memory": self.brain.get_learning_summary,
            "Learning": self.brain.get_learning_summary,
            "Plugins": lambda: {"plugins": self.brain.plugin_manager.list_plugins() if self.brain.plugin_manager else []},
            "Security": self.brain.get_security_summary,
            "Performance": self.brain.get_performance_summary,
        }
        self.dashboards: dict[str, Dashboard] = {}
        self._add_page("Chat", self.chat)
        for name, provider in providers.items():
            panel = Dashboard(f"{name} dashboard", provider); self.dashboards[name] = panel; self._add_page(name, panel)
        self._add_page("Voice", self._voice_page()); self._add_page("Vision", self._vision_page()); self._add_page("Settings", self._settings_page())
        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex); self.navigation.setCurrentRow(0)
        dock = QDockWidget("Navigation", self); dock.setWidget(self.navigation); dock.setMinimumWidth(155)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock); self.setCentralWidget(self.pages)
        notices = QDockWidget("Notifications", self); self.notifications = QPlainTextEdit(readOnly=True); notices.setWidget(self.notifications)
        self.addDockWidget(Qt.BottomDockWidgetArea, notices); self.notify("Studio started")

    def _add_page(self, name: str, page: QWidget) -> None:
        self.navigation.addItem(name); self.pages.addWidget(page)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File"); save = QAction("Save session", self); save.triggered.connect(self.save_session); file_menu.addAction(save)
        refresh = QAction("Refresh dashboards", self); refresh.setShortcut(QKeySequence.Refresh); refresh.triggered.connect(self.refresh_dashboards); self.menuBar().addAction(refresh)

    def _build_toolbar(self) -> None:
        bar = QToolBar("Studio controls", self); self.addToolBar(bar)
        action = QAction("Refresh", self); action.triggered.connect(self.refresh_dashboards); bar.addAction(action)

    def _voice_page(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page); layout.addWidget(QLabel("Voice Center"))
        self.push_to_talk = QPushButton("Push to talk"); self.continuous_listening = QCheckBox("Continuous listening")
        self.voice_status = QLabel("Voice is idle")
        self.push_to_talk.clicked.connect(self._voice_command); layout.addWidget(self.push_to_talk); layout.addWidget(self.continuous_listening); layout.addWidget(self.voice_status); layout.addStretch(); return page

    def _voice_command(self) -> None:
        self.voice_status.setText("Listening…")
        try: result = self.brain.executor.voice_engine.listen() if getattr(self.brain.executor, "voice_engine", None) else None
        except Exception as exc: result = f"Voice unavailable: {exc}"
        self.voice_status.setText(str(result or "Voice engine is unavailable"))

    def _vision_page(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page); layout.addWidget(QLabel("Vision Center")); self.vision_output = QPlainTextEdit(readOnly=True)
        capture = QPushButton("Capture scene"); capture.clicked.connect(self._capture_scene); layout.addWidget(capture); layout.addWidget(self.vision_output); return page

    def _capture_scene(self) -> None:
        try:
            from vision.vision_engine import VisionEngine
            scene = VisionEngine().capture_scene(); self.vision_output.setPlainText(f"Windows: {len(scene.windows)}\nElements: {len(scene.elements)}\nProfile: {scene.metadata.get('profile')}")
        except Exception as exc: self.vision_output.setPlainText(f"Vision unavailable: {exc}")

    def _settings_page(self) -> QWidget:
        page = QWidget(); form = QFormLayout(page); self.performance_ttl = QLineEdit(str(get_config().get("performance", {}).get("cache_ttl", 60)))
        save = QPushButton("Save settings"); save.clicked.connect(self.save_settings); form.addRow("Performance cache TTL", self.performance_ttl); form.addRow(save); return page

    def save_settings(self) -> None:
        config = get_config(); config.setdefault("performance", {})["cache_ttl"] = float(self.performance_ttl.text() or 60); save_config(config); self.notify("Settings saved")

    def notify(self, message: str) -> None:
        self.notifications.appendPlainText(message); self.statusBar().showMessage(message, 3000)

    def refresh_dashboards(self) -> None:
        for dashboard in self.dashboards.values(): dashboard.refresh()

    def save_session(self) -> None:
        self.sessions.save({"page": self.navigation.currentRow(), "geometry": bytes(self.saveGeometry().toBase64()).decode("ascii")}); self.notify("Session saved")

    def _restore_session(self) -> None:
        state = self.sessions.load(); page = state.get("page")
        if isinstance(page, int) and 0 <= page < self.navigation.count(): self.navigation.setCurrentRow(page)

    def closeEvent(self, event) -> None:
        self.save_session(); self.refresh_timer.stop(); event.accept()


def run_studio() -> int:
    app = QApplication.instance() or QApplication([]); window = StudioMainWindow(); window.show(); return app.exec()
