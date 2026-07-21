import json
import tempfile
import unittest
from pathlib import Path

from backend.core.config import AppConfig, SETTINGS_FORMAT, SETTINGS_SCHEMA_VERSION

class ConfigMigrationTests(unittest.TestCase):
    def test_unversioned_settings_migrate_with_safe_pipeline_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text(
                json.dumps({"source_language": "English"}),
                encoding="utf-8",
            )
            cfg = AppConfig(settings_path=str(settings_path))

            cfg.load()
            self.assertTrue(cfg.save())
            migrated = json.loads(settings_path.read_text(encoding="utf-8"))

        self.assertEqual(migrated["format"], SETTINGS_FORMAT)
        self.assertEqual(migrated["schema_version"], SETTINGS_SCHEMA_VERSION)
        self.assertNotIn("pipeline_v2_enabled", migrated)
        self.assertNotIn("pipeline_v2_shadow", migrated)

    def test_newer_settings_schema_is_not_loaded_or_overwritten(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            original = {
                "format": SETTINGS_FORMAT,
                "schema_version": SETTINGS_SCHEMA_VERSION + 1,
                "source_language": "Future language",
                "obsolete_pipeline_flag": True,
            }
            settings_path.write_text(json.dumps(original), encoding="utf-8")
            cfg = AppConfig(source_language="Existing value", settings_path=str(settings_path))

            cfg.load()

            self.assertEqual(cfg.source_language, "Existing value")
            self.assertEqual(cfg.source_language, "Existing value")
            self.assertFalse(cfg.save())
            self.assertEqual(json.loads(settings_path.read_text(encoding="utf-8")), original)

    def test_unknown_settings_format_is_not_loaded_or_overwritten(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            original = {"format": "other-app", "schema_version": 1, "source_language": "Future"}
            settings_path.write_text(json.dumps(original), encoding="utf-8")
            cfg = AppConfig(source_language="Existing", settings_path=str(settings_path))

            cfg.load()

            self.assertEqual(cfg.source_language, "Existing")
            self.assertFalse(cfg.save())
            self.assertEqual(json.loads(settings_path.read_text(encoding="utf-8")), original)

    def test_malformed_settings_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            original = "{not valid json"
            settings_path.write_text(original, encoding="utf-8")
            cfg = AppConfig(settings_path=str(settings_path))

            cfg.load()

            self.assertFalse(cfg.save())
            self.assertEqual(settings_path.read_text(encoding="utf-8"), original)

    def test_unknown_current_schema_fields_survive_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "format": SETTINGS_FORMAT,
                        "schema_version": SETTINGS_SCHEMA_VERSION,
                        "app_version": "0.1.0",
                        "source_language": "Japanese",
                        "future_additive_field": {"enabled": True},
                    }
                ),
                encoding="utf-8",
            )
            cfg = AppConfig(settings_path=str(settings_path))

            cfg.load()
            self.assertTrue(cfg.save())
            saved = json.loads(settings_path.read_text(encoding="utf-8"))

        self.assertEqual(saved["future_additive_field"], {"enabled": True})

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

    def test_schema_v1_fast_ocr_migrates_to_explicit_ppocr(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "format": SETTINGS_FORMAT,
                        "schema_version": 1,
                        "ocr_engine": "fast",
                    }
                ),
                encoding="utf-8",
            )
            cfg = AppConfig(settings_path=str(settings_path))
            cfg.load()

        self.assertEqual(cfg.ocr_engine, "ppocr")

if __name__ == "__main__":
    unittest.main()
