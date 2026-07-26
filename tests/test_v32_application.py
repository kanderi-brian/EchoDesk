import os
import logging
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core import config
from core.app_paths import ensure_data_directories, settings_path
from core.logging_config import category_logger


class ApplicationPackagingTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {"ECHODESK_DATA_DIR": self.root.name}, clear=False)
        self.environment.start(); config._CONFIG = None

    def tearDown(self):
        root_text = self.root.name.casefold()
        base_logger = logging.getLogger("echodesk")
        for handler in list(base_logger.handlers):
            filename = str(getattr(handler, "baseFilename", "")).casefold()
            if filename.startswith(root_text):
                base_logger.removeHandler(handler); handler.close()
        for category in ("startup", "voice", "desktop", "memory", "internet", "vision", "errors"):
            logger = logging.getLogger(f"echodesk.{category}")
            for handler in list(logger.handlers):
                if getattr(handler, "_echodesk_category", None) == category:
                    logger.removeHandler(handler); handler.close()
        config._CONFIG = None; self.environment.stop(); self.root.cleanup()

    def test_user_data_directories_are_writable_and_separate_from_install(self):
        paths = ensure_data_directories()
        self.assertTrue(all(path.is_dir() for path in paths.values()))
        self.assertEqual(Path(self.root.name) / "settings.json", settings_path())

    def test_default_configuration_uses_user_settings_path(self):
        config.save_config({"logging": {"level": "WARNING"}})
        self.assertTrue(settings_path().exists())

    def test_production_category_loggers_exist(self):
        for category in ("startup", "voice", "desktop", "memory", "internet", "vision", "errors"):
            category_logger(category).info("test")
            self.assertTrue((Path(self.root.name) / "logs" / f"{category}.log").exists())

    def test_packaging_files_declare_windows_metadata(self):
        root = Path(__file__).resolve().parents[1]
        self.assertIn("PyInstaller", (root / "release" / "build.ps1").read_text())
        installer = (root / "release" / "EchoDesk.iss").read_text()
        self.assertIn("EchoDesk AI", installer); self.assertIn("startup", installer)
        self.assertIn("ProductName", (root / "release" / "version_info.txt").read_text())


if __name__ == "__main__": unittest.main()
