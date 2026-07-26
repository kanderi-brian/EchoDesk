"""Writable per-user locations for installed EchoDesk builds."""
from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "EchoDesk"


def data_root() -> Path:
    """Return the user-writable application root without touching install files."""
    override = os.environ.get("ECHODESK_DATA_DIR")
    if override:
        return Path(override).expanduser()
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    return Path(base) / APP_NAME if base else Path.home() / ".echodesk"


def ensure_data_directories() -> dict[str, Path]:
    root = data_root()
    paths = {"root": root, "logs": root / "logs", "cache": root / "cache", "temp": root / "temp", "voice": root / "voice"}
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def settings_path() -> Path:
    return ensure_data_directories()["root"] / "settings.json"


def resource_path(relative: str) -> Path:
    """Find a bundled resource in PyInstaller or a source checkout."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return base / relative
