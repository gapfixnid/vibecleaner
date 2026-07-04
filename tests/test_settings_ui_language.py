import unittest
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from routes import settings as settings_route


class SettingsUiLanguageTest(unittest.TestCase):
    def test_get_settings_includes_ui_language(self):
        original = getattr(settings_route.config, "ui_language", None)
        settings_route.config.ui_language = "ko"
        try:
            payload = settings_route.get_settings()
        finally:
            settings_route.config.ui_language = original

        self.assertEqual(payload["ui_language"], "ko")

    def test_update_settings_persists_ui_language(self):
        current = settings_route.get_settings()
        updated = {
            **current,
            "ui_language": "ko",
            "translation_api_key": "",
            "translation_api_key_configured": True,
        }
        schema = settings_route.SettingsSchema(**updated)

        with (
            patch.object(settings_route.config, "save", return_value=True),
            patch.object(settings_route.translation_service, "reload"),
        ):
            response = settings_route.update_settings(schema)

        self.assertEqual(settings_route.config.ui_language, "ko")
        self.assertEqual(response["ui_language"], "ko")


if __name__ == "__main__":
    unittest.main()
