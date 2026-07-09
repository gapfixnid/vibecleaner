import json
import tempfile
import unittest
from pathlib import Path

from backend.core.config import AppConfig

class ConfigMigrationTests(unittest.TestCase):
    def test_removed_high_precision_profiles_migrate_to_balanced_profiles(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "ocr_engine": "high_precision",
                        "inpaint_engine": "aot",
                    }
                ),
                encoding="utf-8",
            )
            cfg = AppConfig(settings_path=str(settings_path))
            cfg.load()

        self.assertEqual(cfg.ocr_engine, "balanced")
        self.assertEqual(cfg.inpaint_engine, "lama")

    def test_existing_settings_without_setup_flag_are_treated_as_completed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "source_language": "Japanese",
                        "target_language": "Korean",
                    }
                ),
                encoding="utf-8",
            )
            cfg = AppConfig(settings_path=str(settings_path))
            cfg.load()

        self.assertTrue(cfg.setup_completed)

if __name__ == "__main__":
    unittest.main()
