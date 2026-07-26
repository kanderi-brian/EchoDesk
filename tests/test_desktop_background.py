import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from desktop.runtime import GlobalHotkeyService, VoiceWakeService
from desktop.single_instance import SingleInstance
from desktop.startup import StartupManager


class _Voice:
    def __init__(self, results): self.results = iter(results); self.started = False; self.stopped = False
    def start(self): self.started = True
    def stop(self): self.stopped = True
    def listen(self):
        try: return next(self.results)
        except StopIteration: time.sleep(.01); return {"success": False, "message": "retry"}


class BackgroundRuntimeTests(unittest.TestCase):
    def test_wake_service_recovers_and_emits_wake_transcript(self):
        voice = _Voice([
            {"success": False, "message": "recognition failure"},
            {"success": True, "wake_word_detected": True, "transcript": "draft an email"},
        ])
        awakened = []
        service = VoiceWakeService(voice, awakened.append)
        service.start(); time.sleep(.4); service.stop()
        self.assertTrue(voice.started); self.assertTrue(voice.stopped)
        self.assertIn("draft an email", awakened)

    def test_single_instance_is_noop_outside_windows(self):
        with patch("desktop.single_instance.os.name", "posix"):
            guard = SingleInstance(); self.assertTrue(guard.acquire()); guard.release()

    def test_startup_command_uses_background_flag(self):
        manager = StartupManager(executable=r"C:\Program Files\EchoDesk\EchoDesk.exe")
        with patch("desktop.startup.sys.frozen", True, create=True):
            self.assertIn("--background", manager.command)

    def test_installer_registers_startup_and_shortcuts(self):
        installer = Path("release/EchoDesk.iss").read_text(encoding="utf-8")
        self.assertIn("CurrentVersion\\Run", installer)
        self.assertIn("{autoprograms}\\EchoDesk", installer)
        self.assertIn("{autodesktop}", installer)

    def test_build_is_windowed_and_has_assets(self):
        spec = Path("release/EchoDesk.spec").read_text(encoding="utf-8")
        self.assertIn("console=False", spec); self.assertIn('"assets"', spec)
        self.assertIn("Qt/lib/fonts", spec)

    def test_desktop_defaults_match_wake_contract(self):
        from core.config import DEFAULT_CONFIG
        desktop = DEFAULT_CONFIG["desktop"]
        self.assertEqual("Hey Echo", desktop["wake_word"])
        self.assertEqual("Ctrl+Shift+Space", desktop["hotkey"])

    def test_global_hotkey_parses_default_contract(self):
        self.assertEqual((6, 0x20), GlobalHotkeyService._keys("Ctrl+Shift+Space"))
