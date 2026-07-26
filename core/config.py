import json
import os
from pathlib import Path
from typing import Any, Dict

from .app_paths import settings_path

DEFAULT_CONFIG = {
    "logging": {"level": "INFO", "dir": None, "max_bytes": 1048576, "backup_count": 5},
    "plugins": {"lazy_load": False},
    "performance": {"cache_ttl": 60.0, "cache_maxsize": 128, "plan_cache_ttl": 120.0},
    "security": {"policy": "balanced"},
    "runtime": {"tick_interval": 5.0},
    "llm": {"request_timeout": 0, "task_timeout": 0},
    "internet": {"timeout": 5.0, "retries": 2},
    "desktop": {"launch_at_startup": False, "listen_on_startup": True, "wake_word": "Hey Echo", "hotkey": "Ctrl+Shift+Space"},
}

_CONFIG: Dict[str, Any] | None = None


def load_config(path: str | None = None) -> Dict[str, Any]:
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG

    cfg_path = Path(path) if path else Path(os.environ.get("ECHODESK_CONFIG", settings_path()))
    config = {key: value.copy() if isinstance(value, dict) else value for key, value in DEFAULT_CONFIG.items()}
    if cfg_path.exists():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # merge shallowly
                for k, v in data.items():
                    if isinstance(v, dict) and isinstance(config.get(k), dict):
                        config[k].update(v)
                    else:
                        config[k] = v
        except Exception:
            # ignore and use defaults
            pass

    # environment overrides
    log_level = os.environ.get("ECHODESK_LOG_LEVEL")
    if log_level:
        config.setdefault("logging", {})["level"] = log_level

    _CONFIG = config
    return _CONFIG


def get_config() -> Dict[str, Any]:
    return load_config()


def save_config(config: Dict[str, Any], path: str | None = None) -> None:
    """Persist settings while retaining the existing lazy configuration API."""
    global _CONFIG
    cfg_path = Path(path) if path else Path(os.environ.get("ECHODESK_CONFIG", settings_path()))
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cfg_path, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2, sort_keys=True)
    _CONFIG = config
