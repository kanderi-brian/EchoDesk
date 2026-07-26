import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    HAS_PYSIDE = True
except ModuleNotFoundError:
    QApplication = None
    HAS_PYSIDE = False


@unittest.skipUnless(HAS_PYSIDE, "PySide6 is required for desktop UI tests")
class DesktopWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ui.floating_window import FloatingAssistantWindow, MicrophoneIndicator, VoiceStatusBridge
        globals().update(FloatingAssistantWindow=FloatingAssistantWindow, MicrophoneIndicator=MicrophoneIndicator, VoiceStatusBridge=VoiceStatusBridge)
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.voice = MagicMock(); self.voice.status.return_value = {"listening": False, "speaking": False}
        self.brain = MagicMock(); self.brain.executor._voice_engine = self.voice

    def test_microphone_uses_supported_voice_states(self):
        indicator = MicrophoneIndicator(); indicator.set_state("Listening")
        self.assertEqual("Listening", indicator.state)
        indicator.set_state("unsupported")
        self.assertEqual("Idle", indicator.state)

    def test_status_bridge_prioritizes_existing_voice_engine_state(self):
        bridge = VoiceStatusBridge(self.voice); states = []; bridge.state_changed.connect(states.append)
        self.voice.status.return_value = {"listening": True, "speaking": False}; bridge.refresh()
        self.assertEqual("Listening", bridge.state)
        self.voice.status.return_value = {"listening": False, "speaking": True}; bridge.refresh()
        self.assertEqual("Speaking", bridge.state); bridge.timer.stop()

    def test_window_is_frameless_topmost_and_closes_to_tray(self):
        window = FloatingAssistantWindow(self.brain, self.voice)
        self.assertTrue(window.windowFlags() & window.windowFlags().FramelessWindowHint)
        self.assertTrue(window.windowFlags() & window.windowFlags().WindowStaysOnTopHint)
        window.show(); self.qt.processEvents(); window.close(); self.qt.processEvents()
        self.assertTrue(window.isHidden()); window.exit_application()

    def test_tray_actions_include_show_hide_and_exit(self):
        window = FloatingAssistantWindow(self.brain, self.voice)
        self.assertEqual("Show EchoDesk", window.show_action.text())
        self.assertEqual("Hide EchoDesk", window.hide_action.text())
        self.assertEqual("Exit EchoDesk", window.exit_action.text()); window.exit_application()


class DesktopStartupTests(unittest.TestCase):
    def test_default_startup_launches_desktop_with_initialized_brain(self):
        import main
        with patch.object(main, "studio_available", return_value=True), patch.object(main, "run_desktop") as desktop, patch("brain.brain.EchoBrain") as brain:
            main.main([])
        desktop.assert_called_once()


if __name__ == "__main__": unittest.main()
