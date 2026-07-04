import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from modules import config as config_module
from modules.config import AppConfig


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
            cfg = AppConfig()

            with patch.object(config_module, "SETTINGS_FILE_PATH", str(settings_path)):
                cfg.load()

        self.assertEqual(cfg.ocr_engine, "balanced")
        self.assertEqual(cfg.inpaint_engine, "lama")


if __name__ == "__main__":
    unittest.main()
