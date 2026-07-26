"""Modern desktop chat shell that adapts, rather than replaces, EchoDesk services."""
from __future__ import annotations

import html
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPropertyAnimation, QThread, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QGuiApplication, QKeySequence, QTextCursor
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout,
    QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QStackedWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget)

from brain.brain import EchoBrain
from core.app_paths import ensure_data_directories
from core.config import get_config, save_config
from desktop.startup import StartupManager


class SessionStore:
    """UI-only persistence for conversations and the last visible workspace."""
    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path) if path else ensure_data_directories()["root"] / "studio_session.json"

    def load(self) -> dict[str, Any]:
        try: return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError): return {}

    def save(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


class ConversationStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or ensure_data_directories()["root"] / "conversations.json"
        self.conversations: list[dict[str, Any]] = self._load()

    def _load(self) -> list[dict[str, Any]]:
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            return loaded if isinstance(loaded, list) else []
        except (OSError, json.JSONDecodeError): return []

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.conversations, indent=2, ensure_ascii=False), encoding="utf-8")

    def new(self) -> dict[str, Any]:
        conversation = {"id": datetime.now(UTC).strftime("%Y%m%d%H%M%S%f"), "title": "New conversation", "messages": [], "updated_at": datetime.now(UTC).isoformat()}
        self.conversations.insert(0, conversation); self.save(); return conversation


class Dashboard(QWidget):
    """Kept for existing backend dashboards and public Studio compatibility."""
    def __init__(self, title: str, provider, parent: QWidget | None = None) -> None:
        super().__init__(parent); self.provider = provider; layout = QVBoxLayout(self); layout.addWidget(QLabel(title))
        self.table = QTableWidget(0, 2); self.table.setHorizontalHeaderLabels(["Metric", "Value"]); self.table.setAccessibleName(title); layout.addWidget(self.table)

    def refresh(self) -> None:
        try: data = self.provider() or {}
        except Exception as exc: data = {"status": f"Unavailable: {exc}"}
        rows = self._flatten(data); self.table.setRowCount(len(rows))
        for index, (key, value) in enumerate(rows): self.table.setItem(index, 0, QTableWidgetItem(key)); self.table.setItem(index, 1, QTableWidgetItem(value))

    @staticmethod
    def _flatten(data: Any, prefix: str = "") -> list[tuple[str, str]]:
        if isinstance(data, dict): return [item for key, value in data.items() for item in Dashboard._flatten(value, f"{prefix}.{key}".strip("."))]
        if isinstance(data, list): return [(prefix, f"{len(data)} item(s)")]
        return [(prefix or "value", str(data))]


def render_markdown(text: str) -> str:
    """Small dependency-free renderer for readable chat, lists, headings, and code."""
    lines, result, code = text.splitlines(), [], False
    for line in lines:
        escaped = html.escape(line)
        if line.startswith("```"):
            result.append("</code></pre>" if code else "<pre><code>"); code = not code; continue
        if code: result.append(escaped); continue
        if line.startswith("### "): result.append(f"<h4>{escaped[4:]}</h4>")
        elif line.startswith("## "): result.append(f"<h3>{escaped[3:]}</h3>")
        elif line.startswith("# "): result.append(f"<h2>{escaped[2:]}</h2>")
        elif line.startswith(("- ", "* ")): result.append(f"<div>• {escaped[2:]}</div>")
        elif len(line) > 2 and line[0].isdigit() and ". " in line[:4]: result.append(f"<div>{escaped}</div>")
        elif line: result.append(f"<div>{escaped}</div>")
        else: result.append("<br>")
    if code: result.append("</code></pre>")
    return "".join(result)


class MessageBubble(QFrame):
    copy_requested = Signal(str)
    def __init__(self, role: str, content: str, parent=None) -> None:
        super().__init__(parent); self.role, self.content = role, content; self.setObjectName("userBubble" if role == "user" else "assistantBubble")
        layout = QVBoxLayout(self); layout.setContentsMargins(14, 10, 14, 8)
        header = QHBoxLayout(); header.addWidget(QLabel("You" if role == "user" else "EchoDesk")); header.addStretch()
        copy = QPushButton("Copy"); copy.setObjectName("quietButton"); copy.clicked.connect(lambda: self.copy_requested.emit(self.content)); header.addWidget(copy); layout.addLayout(header)
        self.body = QLabel(); self.body.setWordWrap(True); self.body.setTextFormat(Qt.RichText); self.body.setText(render_markdown(content)); self.body.setTextInteractionFlags(Qt.TextSelectableByMouse); layout.addWidget(self.body)
        self.setMaximumWidth(760)


class ChatWorkspace(QWidget):
    """ChatGPT-style conversation surface backed by the existing EchoBrain.process API."""
    attachment_added = Signal(str)
    message_added = Signal(str, str)
    class _CommandWorker(QThread):
        completed = Signal(str)
        def __init__(self, brain: EchoBrain, text: str, parent=None) -> None: super().__init__(parent); self.brain, self.text = brain, text
        def run(self) -> None:
            try: response = self.brain.process(self.text)
            except Exception: response = "I couldn't complete that request. Please try again."
            self.completed.emit(str(response))
    class _VoiceWorker(QThread):
        completed = Signal(str)
        def __init__(self, voice, parent=None): super().__init__(parent); self.voice = voice
        def run(self):
            try:
                result = self.voice.listen(); self.completed.emit(str(result.get("transcript", "")) if result.get("success") else "")
            except Exception: self.completed.emit("")

    def __init__(self, brain: EchoBrain, parent: QWidget | None = None) -> None:
        super().__init__(parent); self.brain, self.attachments, self.messages = brain, [], []; self._stream_text = ""; self._stream_index = 0
        self.setAcceptDrops(True); root = QVBoxLayout(self); root.setContentsMargins(22, 20, 22, 18); root.setSpacing(12)
        self.scroll = QScrollArea(widgetResizable=True); self.scroll.setFrameShape(QFrame.NoFrame); self.message_host = QWidget(); self.message_layout = QVBoxLayout(self.message_host); self.message_layout.setSpacing(12); self.message_layout.addStretch(); self.scroll.setWidget(self.message_host); root.addWidget(self.scroll, 1)
        self.typing = QLabel("✦ Echo is thinking..."); self.typing.setObjectName("typingIndicator"); self.typing.hide(); root.addWidget(self.typing)
        composer = QFrame(); composer.setObjectName("composer"); row = QHBoxLayout(composer); self.input = QPlainTextEdit(); self.input.setPlaceholderText("Message EchoDesk…  (Ctrl+Enter to send)"); self.input.setFixedHeight(76); self.input.setAccessibleName("Message input")
        self.send = QPushButton("Send"); self.microphone = QPushButton("◉"); self.attach = QPushButton("＋"); self.screenshot = QPushButton("▣"); self.stop = QPushButton("Stop"); self.stop.setEnabled(False)
        for button, tip in ((self.microphone, "Voice input"), (self.attach, "Attach files"), (self.screenshot, "Attach screenshot")): button.setToolTip(tip); button.setObjectName("iconButton")
        self.send.clicked.connect(self.send_message); self.microphone.clicked.connect(self.start_voice); self.attach.clicked.connect(self.add_attachment); self.screenshot.clicked.connect(self.add_screenshot); self.stop.clicked.connect(self.stop_generation); row.addWidget(self.input, 1); row.addWidget(self.attach); row.addWidget(self.screenshot); row.addWidget(self.microphone); row.addWidget(self.stop); row.addWidget(self.send); root.addWidget(composer)
        self.input.installEventFilter(self); self.stream_timer = QTimer(self); self.stream_timer.timeout.connect(self._stream_next)

    @property
    def transcript(self): return self.message_host  # compatibility surface for older integrations

    def eventFilter(self, watched, event):
        if watched is self.input and event.type() == event.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter) and event.modifiers() & Qt.ControlModifier: self.send_message(); return True
        return super().eventFilter(watched, event)

    def load_messages(self, messages: list[dict[str, str]]) -> None:
        self.messages = list(messages)
        while self.message_layout.count() > 1:
            item = self.message_layout.takeAt(0); widget = item.widget(); widget.deleteLater() if widget else None
        for message in self.messages: self._add_bubble(message["role"], message["content"], persist=False)

    def _add_bubble(self, role: str, content: str, persist: bool = True) -> MessageBubble:
        bubble = MessageBubble(role, content); bubble.copy_requested.connect(lambda value: QApplication.clipboard().setText(value)); row = QHBoxLayout(); row.addStretch() if role == "user" else None; row.addWidget(bubble); row.addStretch() if role != "user" else None
        holder = QWidget(); holder.setLayout(row); self.message_layout.insertWidget(self.message_layout.count() - 1, holder)
        if persist: self.messages.append({"role": role, "content": content, "timestamp": datetime.now(UTC).isoformat()}); self.message_added.emit(role, content)
        QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())); return bubble

    def send_message(self) -> None:
        text = self.input.toPlainText().strip()
        if not text or hasattr(self, "worker") and self.worker.isRunning(): return
        self._add_bubble("user", text); self.input.clear(); self.send.setEnabled(False); self.stop.setEnabled(True); self.typing.show()
        self.worker = self._CommandWorker(self.brain, text, self); self.worker.completed.connect(self._command_completed); self.worker.finished.connect(self.worker.deleteLater); self.worker.start()

    def _command_completed(self, response: str) -> None:
        self.typing.hide(); self.send.setEnabled(True); self.stop.setEnabled(False); self._stream_text, self._stream_index = response, 0; self._stream_bubble = self._add_bubble("assistant", "", persist=False); self.stream_timer.start(14)

    def _stream_next(self) -> None:
        self._stream_index += max(1, len(self._stream_text) // 180)
        visible = self._stream_text[:self._stream_index]; self._stream_bubble.content = visible; self._stream_bubble.body.setText(render_markdown(visible))
        if self._stream_index >= len(self._stream_text): self.stream_timer.stop(); self.messages.append({"role": "assistant", "content": self._stream_text, "timestamp": datetime.now(UTC).isoformat()}); self.message_added.emit("assistant", self._stream_text)
        QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum()))

    def stop_generation(self) -> None:
        if self.stream_timer.isActive(): self.stream_timer.stop(); self.messages.append({"role": "assistant", "content": self._stream_bubble.content, "timestamp": datetime.now(UTC).isoformat()}); self.message_added.emit("assistant", self._stream_bubble.content)
        self.stop.setEnabled(False); self.send.setEnabled(True); self.typing.hide()

    def start_voice(self) -> None:
        voice = getattr(getattr(self.brain, "executor", None), "_voice_engine", None)
        if voice is None:
            from voice.voice_engine import VoiceEngine
            voice = VoiceEngine(); self.brain.executor._voice_engine = voice
        self.typing.setText("◉ Listening..."); self.typing.show(); self.voice_worker = self._VoiceWorker(voice, self); self.voice_worker.completed.connect(self._voice_complete); self.voice_worker.start()

    def _voice_complete(self, transcript: str) -> None:
        self.typing.setText("✦ Echo is thinking..."); self.typing.hide()
        if transcript: self.input.setPlainText(transcript); self.send_message()

    def add_attachment(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Attach a file", "", "Supported files (*.png *.jpg *.jpeg *.pdf *.txt);;All files (*)")
        if path: self.attach_file(path)

    def add_screenshot(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen:
            path = ensure_data_directories()["temp"] / f"screenshot-{datetime.now(UTC).strftime('%H%M%S')}.png"; screen.grabWindow(0).save(str(path)); self.attach_file(str(path))

    def attach_file(self, path: str) -> None:
        if path not in self.attachments:
            self.attachments.append(path); self.attachment_added.emit(path); self._add_bubble("user", f"Attached: **{Path(path).name}**")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if url.isLocalFile(): self.attach_file(url.toLocalFile())
        event.acceptProposedAction()


class StudioMainWindow(QMainWindow):
    """Responsive ChatGPT-style desktop shell using the existing EchoDesk backend."""
    def __init__(self, brain: EchoBrain | None = None, session_path: str | None = None) -> None:
        super().__init__(); self.brain = brain or EchoBrain(); self.sessions = SessionStore(session_path); self.conversations = ConversationStore(); self.active: dict[str, Any] | None = None
        self.setWindowTitle("EchoDesk Studio"); self.resize(1360, 860); self.setMinimumSize(900, 600); self._build_shell(); self._restore_session(); self.refresh_timer = QTimer(self); self.refresh_timer.timeout.connect(self.refresh_dashboards); self.refresh_timer.start(3000)

    def _build_shell(self) -> None:
        root = QWidget(); layout = QHBoxLayout(root); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(0); self.setCentralWidget(root)
        sidebar = QFrame(); sidebar.setObjectName("sidebar"); sidebar.setFixedWidth(278); side = QVBoxLayout(sidebar); side.setContentsMargins(14, 16, 14, 14)
        title = QLabel("EchoDesk"); title.setObjectName("brand"); side.addWidget(title); new = QPushButton("＋  New chat"); new.setObjectName("newChatButton"); new.clicked.connect(self.new_chat); side.addWidget(new)
        self.search = QLineEdit(); self.search.setPlaceholderText("Search conversations"); self.search.textChanged.connect(self._render_conversation_list); side.addWidget(self.search)
        self.conversation_list = QListWidget(); self.conversation_list.setObjectName("conversationList"); self.conversation_list.itemClicked.connect(self._select_conversation); side.addWidget(self.conversation_list, 1)
        actions = QHBoxLayout(); rename = QPushButton("Rename"); delete = QPushButton("Delete"); export = QPushButton("Export"); rename.clicked.connect(self.rename_chat); delete.clicked.connect(self.delete_chat); export.clicked.connect(self.export_chat); [actions.addWidget(x) for x in (rename, delete, export)]; side.addLayout(actions)
        self.navigation = QListWidget(); self.navigation.setObjectName("navigation"); [self.navigation.addItem(name) for name in ("Chat", "Plugins", "Memory", "About", "Settings", "Projects", "Agents", "Learning", "Security", "Performance")]; side.addWidget(self.navigation); layout.addWidget(sidebar)
        self.pages = QStackedWidget(); self.chat = ChatWorkspace(self.brain); self.chat.message_added.connect(self._persist_active); self.pages.addWidget(self.chat); self.dashboards: dict[str, Dashboard] = {}
        for name, provider in {"Plugins": lambda: {"plugins": self.brain.plugin_manager.list_plugins() if self.brain.plugin_manager else []}, "Memory": self.brain.get_learning_summary}.items(): panel = Dashboard(name, provider); self.dashboards[name] = panel; self.pages.addWidget(panel)
        self.pages.addWidget(self._about_page()); self.pages.addWidget(self._settings_page())
        for name, provider in {"Projects": lambda: {"goals": self.brain.list_goals(), "progress": self.brain.get_progress()}, "Agents": self.brain.get_agent_metrics, "Learning": self.brain.get_learning_summary, "Security": self.brain.get_security_summary, "Performance": self.brain.get_performance_summary}.items(): panel = Dashboard(name, provider); self.dashboards[name] = panel; self.pages.addWidget(panel)
        layout.addWidget(self.pages, 1); self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        self._apply_theme("dark" if get_config().get("appearance", "dark") != "light" else "light"); self._render_conversation_list()

    def _about_page(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.addWidget(QLabel("<h2>EchoDesk</h2><p>Your local desktop assistant.</p>")); layout.addStretch(); return page

    def _settings_page(self):
        page = QWidget(); form = QFormLayout(page); self.theme = QComboBox(); self.theme.addItems(["Dark", "Light"]); self.launch_at_startup = QCheckBox("Launch EchoDesk when I sign in"); self.wake_word = QLineEdit(str(get_config().get("desktop", {}).get("wake_word", "Hey Echo"))); self.voice_enabled = QCheckBox("Enable voice"); self.voice_enabled.setChecked(True); self.model = QLineEdit("phi3:latest"); save = QPushButton("Save settings"); save.clicked.connect(self.save_settings)
        form.addRow("Theme", self.theme); form.addRow(self.launch_at_startup); form.addRow("Wake word", self.wake_word); form.addRow(self.voice_enabled); form.addRow("LLM model", self.model); form.addRow(save); return page

    def _apply_theme(self, theme: str) -> None:
        light = theme == "light"; self.setStyleSheet(f"""
            QMainWindow {{ background: {'#f7f7f8' if light else '#212121'}; color: {'#202123' if light else '#ececf1'}; }}
            #sidebar {{ background: {'#ececf1' if light else '#171717'}; }} #brand {{ font-size: 22px; font-weight: 700; padding: 6px; }}
            QPushButton {{ border: 0; border-radius: 8px; padding: 9px; background: {'#e3e3e8' if light else '#303030'}; color: {'#202123' if light else '#ececf1'}; }} QPushButton:hover {{ background: #10a37f; color: white; }}
            #newChatButton {{ background: #10a37f; color: white; font-weight: 600; }} QLineEdit, QPlainTextEdit {{ border: 1px solid {'#d9d9e3' if light else '#4a4a4a'}; border-radius: 10px; padding: 8px; background: {'white' if light else '#2f2f2f'}; color: {'#202123' if light else '#ececf1'}; }}
            QListWidget {{ border: 0; background: transparent; }} QListWidget::item {{ padding: 8px; border-radius: 6px; }} QListWidget::item:selected {{ background: #10a37f; color: white; }} #composer {{ background: {'#f7f7f8' if light else '#212121'}; }} #userBubble {{ background: #10a37f; color: white; border-radius: 14px; }} #assistantBubble {{ background: {'#ececf1' if light else '#303030'}; border-radius: 14px; }} #quietButton {{ padding: 3px 7px; background: transparent; }} #typingIndicator {{ color: #10a37f; font-style: italic; padding: 4px; }}
        """)

    def _render_conversation_list(self):
        query = self.search.text().casefold() if hasattr(self, "search") else ""; self.conversation_list.clear()
        for conversation in self.conversations.conversations:
            if query and query not in conversation.get("title", "").casefold(): continue
            item = QListWidgetItem(conversation.get("title", "New conversation")); item.setData(Qt.UserRole, conversation["id"]); self.conversation_list.addItem(item)

    def new_chat(self):
        self.active = self.conversations.new(); self.chat.load_messages([]); self._render_conversation_list(); self.navigation.setCurrentRow(0); self.chat.input.setFocus()

    def _select_conversation(self, item):
        self.active = next((chat for chat in self.conversations.conversations if chat["id"] == item.data(Qt.UserRole)), None)
        if self.active: self.chat.load_messages(self.active.get("messages", [])); self.navigation.setCurrentRow(0)

    def _persist_active(self, role: str = "", content: str = ""):
        if self.active is None: self.active = self.conversations.new()
        self.active["messages"] = self.chat.messages; self.active["updated_at"] = datetime.now(UTC).isoformat()
        if self.active["title"] == "New conversation" and self.chat.messages: self.active["title"] = self.chat.messages[0]["content"][:42]
        self.conversations.save(); self._render_conversation_list()

    def rename_chat(self):
        if not self.active: return
        title, ok = QFileDialog.getSaveFileName(self, "Rename conversation", self.active["title"])
        if ok and title: self.active["title"] = Path(title).name; self.conversations.save(); self._render_conversation_list()

    def delete_chat(self):
        if not self.active: return
        self.conversations.conversations = [chat for chat in self.conversations.conversations if chat["id"] != self.active["id"]]; self.conversations.save(); self.active = None; self.chat.load_messages([]); self._render_conversation_list()

    def export_chat(self):
        if not self.active: return
        path, _ = QFileDialog.getSaveFileName(self, "Export conversation", f"{self.active['title']}.md", "Markdown (*.md)")
        if path: Path(path).write_text("\n\n".join(f"## {'You' if m['role'] == 'user' else 'EchoDesk'}\n\n{m['content']}" for m in self.active["messages"]), encoding="utf-8")

    def save_settings(self):
        config = get_config(); config["appearance"] = self.theme.currentText().lower(); config.setdefault("desktop", {}).update({"launch_at_startup": self.launch_at_startup.isChecked(), "wake_word": self.wake_word.text().strip() or "Hey Echo"}); StartupManager().set_enabled(self.launch_at_startup.isChecked()); save_config(config); self._apply_theme(config["appearance"])

    def refresh_dashboards(self):
        for panel in self.dashboards.values(): panel.refresh()

    def notify(self, message: str): self.statusBar().showMessage(message, 3000)
    def save_session(self): self.sessions.save({"active": self.active["id"] if self.active else None, "page": self.navigation.currentRow(), "geometry": bytes(self.saveGeometry().toBase64()).decode("ascii")})
    def _restore_session(self):
        state = self.sessions.load(); active_id = state.get("active"); self.active = next((chat for chat in self.conversations.conversations if chat["id"] == active_id), None)
        page = state.get("page")
        if isinstance(page, int) and 0 <= page < self.navigation.count(): self.navigation.setCurrentRow(page)
        if self.active: self.chat.load_messages(self.active.get("messages", []))
        else: self.new_chat()
    def closeEvent(self, event): self.save_session(); self.refresh_timer.stop(); event.accept()


def run_studio() -> int:
    app = QApplication.instance() or QApplication([]); window = StudioMainWindow(); window.show(); return app.exec()
