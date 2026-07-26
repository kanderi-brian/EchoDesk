import logging
import logging.handlers
import os
from pathlib import Path
from typing import Optional

from .config import get_config
from .app_paths import ensure_data_directories


def setup_logging(level: Optional[str] = None) -> None:
    cfg = get_config()
    log_cfg = cfg.get("logging", {})
    level_name = (level or log_cfg.get("level") or "INFO").upper()
    level_val = getattr(logging, level_name, logging.INFO)

    log_dir = Path(log_cfg["dir"]) if log_cfg.get("dir") else ensure_data_directories()["logs"]
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("echodesk")
    if logger.handlers:
        # already configured
        logger.setLevel(level_val)
        return

    logger.setLevel(level_val)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.setLevel(level_val)
    logger.addHandler(console)

    log_file = log_dir / "echodesk.log"
    max_bytes = int(log_cfg.get("max_bytes", 1048576))
    backups = int(log_cfg.get("backup_count", 3))

    file_handler = logging.handlers.RotatingFileHandler(
        filename=str(log_file), maxBytes=max_bytes, backupCount=backups, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(level_val)
    logger.addHandler(file_handler)

    # propagate to root so other modules use the same handlers by name
    logging.getLogger().setLevel(level_val)


def category_logger(category: str) -> logging.Logger:
    """Return a rotating production logger dedicated to one support category."""
    setup_logging()
    logger = logging.getLogger(f"echodesk.{category}")
    if any(getattr(handler, "_echodesk_category", None) == category for handler in logger.handlers):
        return logger
    cfg = get_config().get("logging", {})
    handler = logging.handlers.RotatingFileHandler(
        ensure_data_directories()["logs"] / f"{category}.log",
        maxBytes=int(cfg.get("max_bytes", 1048576)), backupCount=int(cfg.get("backup_count", 5)), encoding="utf-8",
    )
    handler._echodesk_category = category  # type: ignore[attr-defined]
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(handler); logger.setLevel(getattr(logging, str(cfg.get("level", "INFO")).upper(), logging.INFO))
    return logger
