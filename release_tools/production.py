"""Safe, dependency-free production support utilities."""
from __future__ import annotations
import json
import platform
from pathlib import Path
import sys
import zipfile
from typing import Any

from core.config import get_config, save_config

PROFILES = {
    "development": {"logging": {"level": "DEBUG"}, "plugins": {"lazy_load": False}, "security": {"policy": "balanced"}},
    "testing": {"logging": {"level": "WARNING"}, "plugins": {"lazy_load": True}, "security": {"policy": "safe"}},
    "production": {"logging": {"level": "INFO"}, "plugins": {"lazy_load": True}, "security": {"policy": "balanced"}},
}
BACKUP_FILES = ("config.json", "memory.db", "memory.json", "history/history.json", "goal_manager/goals.json", "studio_session.json")


def _merge(target: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    for key, value in values.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict): _merge(target[key], value)
        else: target[key] = value
    return target


def apply_profile(name: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Apply one named profile without changing unknown user settings."""
    normalized = name.strip().lower()
    if normalized not in PROFILES: raise ValueError(f"Unknown release profile: {name}")
    return _merge(dict(config or get_config()), PROFILES[normalized])


class ConfigurationWizard:
    """Non-UI first-run configuration model used by Studio or installers."""
    FIELDS = ("llm_provider", "model", "voice_enabled", "vision_enabled", "plugin_directory", "security_policy", "appearance", "data_directory")
    def build(self, **values: Any) -> dict[str, Any]:
        unknown = set(values) - set(self.FIELDS)
        if unknown: raise ValueError(f"Unsupported configuration fields: {sorted(unknown)}")
        result = get_config().copy(); result["setup_complete"] = True
        result["llm"] = {"provider": values.get("llm_provider", "ollama"), "model": values.get("model", "")}
        result["voice"] = {"enabled": bool(values.get("voice_enabled", True))}; result["vision"] = {"enabled": bool(values.get("vision_enabled", True))}
        result["plugins"] = {**result.get("plugins", {}), "directory": values.get("plugin_directory", "plugins")}
        result["security"] = {**result.get("security", {}), "policy": values.get("security_policy", result.get("security", {}).get("policy", "balanced"))}
        result["appearance"] = values.get("appearance", "system"); result["data_directory"] = values.get("data_directory", ".")
        return result
    def persist(self, **values: Any) -> dict[str, Any]:
        config = self.build(**values); save_config(config); return config


class BackupManager:
    """Creates validated ZIP backups containing only known local user data."""
    def __init__(self, root: str | Path = ".") -> None: self.root = Path(root)
    def create(self, destination: str | Path, include_plugins: bool = False) -> Path:
        destination = Path(destination); destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in BACKUP_FILES:
                source = self.root / name
                if source.is_file(): archive.write(source, name)
            if include_plugins:
                plugins = self.root / "plugins"
                if plugins.is_dir():
                    for source in plugins.rglob("*"):
                        if source.is_file() and "__pycache__" not in source.parts: archive.write(source, source.relative_to(self.root).as_posix())
        return destination
    def validate(self, source: str | Path) -> list[str]:
        with zipfile.ZipFile(source) as archive:
            names = archive.namelist()
            if not names: raise ValueError("Backup is empty")
            for name in names:
                path = Path(name)
                if path.is_absolute() or ".." in path.parts: raise ValueError("Backup contains unsafe paths")
            return names
    def restore(self, source: str | Path) -> list[Path]:
        names = self.validate(source); restored = []
        with zipfile.ZipFile(source) as archive:
            for name in names:
                target = self.root / name; target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(name) as incoming, open(target, "wb") as outgoing: outgoing.write(incoming.read())
                restored.append(target)
        return restored


class RecoveryManager:
    """Persists only safe UI/session state atomically for crash recovery."""
    def __init__(self, path: str | Path = "studio_recovery.json") -> None: self.path = Path(path)
    def save(self, state: dict[str, Any]) -> None:
        temp = self.path.with_suffix(self.path.suffix + ".tmp"); temp.write_text(json.dumps(state), encoding="utf-8"); temp.replace(self.path)
    def restore(self) -> dict[str, Any]:
        try: return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError): return {}


class Diagnostics:
    """Produces a redaction-safe support report from existing runtime summaries."""
    @staticmethod
    def collect(brain: Any | None = None) -> dict[str, Any]:
        report: dict[str, Any] = {"version": "3.2.0", "python": sys.version.split()[0], "platform": platform.platform(), "configuration_valid": isinstance(get_config(), dict)}
        if brain is not None:
            report.update({"plugins": brain.plugin_manager.list_plugins() if getattr(brain, "plugin_manager", None) else [], "agents": brain.get_agent_metrics(), "security": brain.get_security_summary(), "performance": brain.get_performance_summary()})
        return report
    @staticmethod
    def write(destination: str | Path, brain: Any | None = None) -> Path:
        destination = Path(destination); destination.write_text(json.dumps(Diagnostics.collect(brain), indent=2, default=str), encoding="utf-8"); return destination
