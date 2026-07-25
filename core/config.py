import json
import os
from pathlib import Path
from typing import Any, Dict

DEFAULT_CONFIG = {
    "logging": {"level": "INFO", "dir": "logs", "max_bytes": 1048576, "backup_count": 3},
    "plugins": {"lazy_load": False},
    "performance": {"cache_ttl": 60.0, "cache_maxsize": 128, "plan_cache_ttl": 120.0},
    "security": {"policy": "balanced"},
    "runtime": {"tick_interval": 5.0},
}

_CONFIG: Dict[str, Any] | None = None


def load_config(path: str | None = None) -> Dict[str, Any]:
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG

    cfg_path = Path(path) if path else Path(os.environ.get("ECHODESK_CONFIG", "config.json"))
    config = DEFAULT_CONFIG.copy()
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
