"""
EchoDesk v2.0 - Modern GUI Interface

Provides a modern chat-based interface to EchoDesk with:
- Conversation history
- Memory panel
- Status indicators
- Voice and screen buttons
- Dark theme
- Responsive layout
"""

from PySide6.QtWidgets import (
    QMainWindow,
    QPushButton,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QSplitter,
    QListWidget,
    QListWidgetItem,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor

from echodesk import EchoDesk


class MainWindow(QMainWindow):
    """Main window for EchoDesk v2.0 GUI."""

    def __init__(self):
        """Initialize the main window."""
        super().__init__()

        # Initialize EchoDesk
        self.app = EchoDesk()
        self.app.start()

        # Window setup
        self.setWindowTitle("EchoDesk v2.0")
        self.setGeometry(200, 100, 1200, 700)
        self.setStyleSheet(self._get_dark_theme())

        # Initialize UI components
        self._setup_ui()

        # Status update timer
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_status)
        self.timer.start(1000)

    def _setup_ui(self):
        """Setup the user interface."""
        # Main container
        container = QWidget()
        main_layout = QHBoxLayout()

        # Left side: Chat and input
        left_layout = QVBoxLayout()

        # Title
        title = QLabel("EchoDesk v2.0")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        left_layout.addWidget(title)

        # Chat display
        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        self.chat.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #e0e0e0;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        left_layout.addWidget(self.chat)

        # Input area
        input_layout = QHBoxLayout()

        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask EchoDesk something...")
        self.input.setStyleSheet("""
            QLineEdit {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 6px;
                font-size: 11pt;
            }
            QLineEdit:focus {
                border: 1px solid #0d7377;
            }
        """)
        self.input.returnPressed.connect(self._process_command)
        input_layout.addWidget(self.input)

        # Buttons
        self.send_button = QPushButton("Send")
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #0d7377;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #14919b;
            }
            QPushButton:pressed {
                background-color: #0a5860;
            }
        """)
        self.send_button.clicked.connect(self._process_command)
        input_layout.addWidget(self.send_button)

        self.screen_button = QPushButton("📸 Screen")
        self.screen_button.setMaximumWidth(100)
        self.screen_button.setStyleSheet("""
            QPushButton {
                background-color: #3d3d3d;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 8px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        self.screen_button.clicked.connect(self._read_screen)
        input_layout.addWidget(self.screen_button)

        self.voice_button = QPushButton("🎙️ Voice")
        self.voice_button.setMaximumWidth(100)
        self.voice_button.setStyleSheet("""
            QPushButton {
                background-color: #3d3d3d;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 8px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        self.voice_button.clicked.connect(self._process_voice)
        input_layout.addWidget(self.voice_button)

        left_layout.addLayout(input_layout)

        # Right side: Memory panel and status
        right_layout = QVBoxLayout()
        right_layout.setMaximumWidth(300)

        # Status panel
        status_label = QLabel("System Status")
        status_font = QFont()
        status_font.setBold(True)
        status_label.setFont(status_font)
        right_layout.addWidget(status_label)

        self.status_text = QLabel()
        self.status_text.setStyleSheet("""
            QLabel {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 8px;
                font-family: monospace;
                font-size: 10pt;
            }
        """)
        right_layout.addWidget(self.status_text)

        # Memory panel
        memory_label = QLabel("Memory")
        memory_label.setFont(status_font)
        right_layout.addWidget(memory_label)

        self.memory_list = QListWidget()
        self.memory_list.setStyleSheet("""
            QListWidget {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #0d7377;
            }
        """)
        right_layout.addWidget(self.memory_list)

        # Launch button
        self.launch_button = QPushButton("🚀 Launch App")
        self.launch_button.setStyleSheet("""
            QPushButton {
                background-color: #3d3d3d;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        self.launch_button.clicked.connect(self._launch_app)
        right_layout.addWidget(self.launch_button)

        right_layout.addStretch()

        # Combine left and right
        left_widget = QWidget()
        left_widget.setLayout(left_layout)

        right_widget = QWidget()
        right_widget.setLayout(right_layout)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)
        container.setLayout(main_layout)

        self.setCentralWidget(container)

    def _process_command(self):
        """Process a user command."""
        command = self.input.text().strip()

        if command:
            self.chat.append(f"<span style='color: #0d7377'><b>You:</b></span> {command}")

            try:
                result = self.app.process(command)
                if result.get("success"):
                    message = result.get("message", "Command processed.")
                    self.chat.append(f"<span style='color: #4ecca3'><b>EchoDesk:</b></span> {message}")
                else:
                    message = result.get("message", "Error processing command.")
                    self.chat.append(f"<span style='color: #ff6b6b'><b>Error:</b></span> {message}")
            except Exception as e:
                self.chat.append(f"<span style='color: #ff6b6b'><b>Error:</b></span> {str(e)}")

            self.input.clear()
            # Scroll to bottom
            self.chat.verticalScrollBar().setValue(self.chat.verticalScrollBar().maximum())

    def _read_screen(self):
        """Read text from the screen."""
        self.chat.append("<span style='color: #0d7377'><b>EchoDesk:</b></span> Reading screen...")

        try:
            result = self.app.read_screen()
            if result.get("success"):
                text = result.get("result", "No text found.")
                self.chat.append(f"<span style='color: #4ecca3'><b>Screen Text:</b></span> {text[:500]}")
            else:
                message = result.get("message", "Failed to read screen.")
                self.chat.append(f"<span style='color: #ff6b6b'><b>Error:</b></span> {message}")
        except Exception as e:
            self.chat.append(f"<span style='color: #ff6b6b'><b>Error:</b></span> {str(e)}")

        self.chat.verticalScrollBar().setValue(self.chat.verticalScrollBar().maximum())

    def _process_voice(self):
        """Process voice input."""
        self.chat.append("<span style='color: #0d7377'><b>EchoDesk:</b></span> Listening...")

        try:
            result = self.app.process_voice()
            if result.get("success"):
                message = result.get("message", "Voice processed.")
                self.chat.append(f"<span style='color: #4ecca3'><b>Response:</b></span> {message}")
            else:
                message = result.get("message", "Voice processing failed.")
                self.chat.append(f"<span style='color: #ff6b6b'><b>Error:</b></span> {message}")
        except Exception as e:
            self.chat.append(f"<span style='color: #ff6b6b'><b>Error:</b></span> {str(e)}")

        self.chat.verticalScrollBar().setValue(self.chat.verticalScrollBar().maximum())

    def _launch_app(self):
        """Prompt to launch an application."""
        self.input.setPlaceholderText("Type app name (e.g., 'chrome', 'notepad')...")
        self.input.setFocus()

    def _update_status(self):
        """Update the system status display."""
        status = self.app.status()
        subsystems = status["subsystems"]
        active = status["subsystems_active"]
        total = status["subsystems_total"]

        status_html = f"""
        <b>Status:</b> {'Running' if status['running'] else 'Stopped'}<br>
        <b>Active:</b> {active}/{total}<br>
        <br>
        <b>Subsystems:</b><br>
        """

        for name, available in subsystems.items():
            icon = "✓" if available else "✗"
            color = "#4ecca3" if available else "#ff6b6b"
            status_html += f"<span style='color: {color}'>{icon} {name.capitalize()}</span><br>"

        self.status_text.setText(status_html)

    def _get_dark_theme(self) -> str:
        """Return a dark theme stylesheet."""
        return """
            QMainWindow {
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
            QLabel {
                color: #e0e0e0;
            }
            QPushButton {
                font-weight: bold;
            }
        """

    def closeEvent(self, event):
        """Handle window close event."""
        self.app.shutdown()
        self.timer.stop()
        event.accept()