import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from release_tools.production import (BACKUP_FILES, BackupManager, ConfigurationWizard,
    Diagnostics, PROFILES, RecoveryManager, apply_profile)


class Phase23ReleaseTests(unittest.TestCase):
    def test_profiles_are_available(self): self.assertEqual({"development", "testing", "production"}, set(PROFILES))
    def test_unknown_profile_is_rejected(self):
        with self.assertRaises(ValueError): apply_profile("unknown", {})
    def test_production_profile_enables_lazy_plugins(self): self.assertTrue(apply_profile("production", {})["plugins"]["lazy_load"])
    def test_testing_profile_is_safe(self): self.assertEqual("safe", apply_profile("testing", {})["security"]["policy"])
    def test_wizard_marks_setup_complete(self): self.assertTrue(ConfigurationWizard().build()["setup_complete"])
    def test_wizard_rejects_unknown_options(self):
        with self.assertRaises(ValueError): ConfigurationWizard().build(unknown=True)
    def test_diagnostics_has_release_version(self): self.assertEqual("3.2.0", Diagnostics.collect()["version"])
    def test_diagnostics_can_write_json(self):
        with tempfile.TemporaryDirectory() as root:
            path = Diagnostics.write(Path(root) / "report.json")
            self.assertEqual("3.2.0", json.loads(path.read_text())["version"])
    def test_recovery_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            recovery = RecoveryManager(Path(root) / "state.json"); recovery.save({"page": 4}); self.assertEqual({"page": 4}, recovery.restore())
    def test_recovery_handles_missing_state(self):
        with tempfile.TemporaryDirectory() as root: self.assertEqual({}, RecoveryManager(Path(root) / "missing.json").restore())
    def test_backup_validation_rejects_empty_archive(self):
        with tempfile.TemporaryDirectory() as root:
            archive = Path(root) / "empty.zip"
            with zipfile.ZipFile(archive, "w"): pass
            with self.assertRaises(ValueError): BackupManager(root).validate(archive)
    def test_backup_validation_rejects_unsafe_path(self):
        with tempfile.TemporaryDirectory() as root:
            archive = Path(root) / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as handle: handle.writestr("../unsafe", "x")
            with self.assertRaises(ValueError): BackupManager(root).validate(archive)
    def test_backup_and_restore_round_trip(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as restore:
            Path(root, "memory.json").write_text('{"safe": true}')
            archive = BackupManager(root).create(Path(root) / "backup.zip")
            BackupManager(restore).restore(archive)
            self.assertEqual('{"safe": true}', Path(restore, "memory.json").read_text())
    def test_manifest_is_current(self):
        manifest = json.loads(Path("release/manifest.json").read_text())
        self.assertEqual("3.2.0", manifest["version"])
    def test_manifest_never_embeds_secrets(self): self.assertFalse(json.loads(Path("release/manifest.json").read_text())["secrets_embedded"])


def _wizard_field_test(field, value):
    def test(self):
        config = ConfigurationWizard().build(**{field: value})
        self.assertTrue(config["setup_complete"])
    return test


# Individual field permutations protect the first-run configuration contract.
for _field, _values in {
    "llm_provider": ["ollama", "local", "none"], "model": ["", "small", "large"],
    "voice_enabled": [True, False, True], "vision_enabled": [True, False, True],
    "plugin_directory": ["plugins", "custom", "extensions"],
    "security_policy": ["safe", "balanced", "unrestricted"],
    "appearance": ["system", "dark", "light"], "data_directory": [".", "data", "profile"],
}.items():
    for _index, _value in enumerate(_values):
        setattr(Phase23ReleaseTests, f"test_wizard_{_field}_{_index}", _wizard_field_test(_field, _value))

for _profile in ("development", "testing", "production"):
    def _profile_test(self, name=_profile):
        self.assertIn("logging", apply_profile(name, {}))
    setattr(Phase23ReleaseTests, f"test_profile_shape_{_profile}", _profile_test)


if __name__ == "__main__": unittest.main()
