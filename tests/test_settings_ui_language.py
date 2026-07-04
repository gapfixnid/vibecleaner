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

    def test_get_settings_includes_pipeline_options(self):
        originals = {
            "detect_model": settings_route.config.detect_model,
            "ocr_engine": getattr(settings_route.config, "ocr_engine", "auto"),
            "inpaint_engine": getattr(settings_route.config, "inpaint_engine", "lama"),
            "ocr_crop_scale": getattr(settings_route.config, "ocr_crop_scale", 1.0),
            "text_direction_override": getattr(settings_route.config, "text_direction_override", "auto"),
            "adaptive_binarization": settings_route.config.adaptive_binarization,
            "adaptive_binarization_strength": getattr(
                settings_route.config,
                "adaptive_binarization_strength",
                2.0,
            ),
        }
        settings_route.config.detect_model = "Small (INT8)"
        settings_route.config.ocr_engine = "ppocr"
        settings_route.config.inpaint_engine = "opencv"
        settings_route.config.ocr_crop_scale = 1.25
        settings_route.config.text_direction_override = "horizontal"
        settings_route.config.adaptive_binarization = False
        settings_route.config.adaptive_binarization_strength = 3.0
        try:
            payload = settings_route.get_settings()
        finally:
            for key, value in originals.items():
                setattr(settings_route.config, key, value)

        self.assertEqual(payload["detect_model"], "Small (INT8)")
        self.assertEqual(payload["ocr_engine"], "ppocr")
        self.assertEqual(payload["inpaint_engine"], "opencv")
        self.assertEqual(payload["ocr_crop_scale"], 1.25)
        self.assertEqual(payload["text_direction_override"], "horizontal")
        self.assertFalse(payload["adaptive_binarization"])
        self.assertEqual(payload["adaptive_binarization_strength"], 3.0)

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

    def test_update_settings_persists_pipeline_options(self):
        current = settings_route.get_settings()
        updated = {
            **current,
            "detect_model": "Small (INT8)",
            "ocr_engine": "manga_ocr",
            "inpaint_engine": "opencv",
            "ocr_crop_scale": 1.75,
            "text_direction_override": "vertical",
            "adaptive_binarization": True,
            "adaptive_binarization_strength": 2.75,
            "translation_api_key": "",
            "translation_api_key_configured": True,
        }
        schema = settings_route.SettingsSchema(**updated)

        with (
            patch.object(settings_route.config, "save", return_value=True),
            patch.object(settings_route.translation_service, "reload"),
        ):
            response = settings_route.update_settings(schema)

        self.assertEqual(settings_route.config.detect_model, "Small (INT8)")
        self.assertEqual(settings_route.config.ocr_engine, "manga_ocr")
        self.assertEqual(settings_route.config.inpaint_engine, "opencv")
        self.assertEqual(settings_route.config.ocr_crop_scale, 1.75)
        self.assertEqual(settings_route.config.text_direction_override, "vertical")
        self.assertTrue(settings_route.config.adaptive_binarization)
        self.assertEqual(settings_route.config.adaptive_binarization_strength, 2.75)
        self.assertEqual(response["ocr_engine"], "manga_ocr")
        self.assertEqual(response["inpaint_engine"], "opencv")


if __name__ == "__main__":
    unittest.main()
