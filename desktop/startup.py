"""Windows sign-in registration for the installed EchoDesk executable."""
from __future__ import annotations

import os
import sys
from pathlib import Path


class StartupManager:
    """Register the current executable without requiring administrator rights."""

    RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    VALUE_NAME = "EchoDesk"

    def __init__(self, executable: str | None = None) -> None:
        self.executable = executable or sys.executable

    @property
    def command(self) -> str:
        # A source checkout needs Python plus main.py; a frozen build is already an exe.
        if getattr(sys, "frozen", False):
            return f'"{self.executable}" --background'
        return f'"{self.executable}" "{Path(__file__).resolve().parents[1] / "main.py"}" --background'

    def enabled(self) -> bool:
        if os.name != "nt":
            return False
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.RUN_KEY) as key:
                return bool(winreg.QueryValueEx(key, self.VALUE_NAME)[0])
        except OSError:
            return False

    def set_enabled(self, enabled: bool) -> bool:
        """Enable/disable per-user startup. Returns False on unsupported platforms."""
        if os.name != "nt":
            return False
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.RUN_KEY) as key:
            if enabled:
                winreg.SetValueEx(key, self.VALUE_NAME, 0, winreg.REG_SZ, self.command)
            else:
                try:
                    winreg.DeleteValue(key, self.VALUE_NAME)
                except FileNotFoundError:
                    pass
        return True
