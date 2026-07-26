"""Per-user single-instance guard used by the Windows desktop entrypoint."""
from __future__ import annotations

import ctypes
import os


class SingleInstance:
    """Use a named Windows mutex; harmlessly degrades for non-Windows test runs."""
    def __init__(self, name: str = "Local\\EchoDesk.Desktop") -> None:
        self.name = name
        self._handle = None

    def acquire(self) -> bool:
        if os.name != "nt":
            return True
        kernel32 = ctypes.windll.kernel32
        self._handle = kernel32.CreateMutexW(None, False, self.name)
        return ctypes.get_last_error() != 183

    def release(self) -> None:
        if self._handle:
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None
