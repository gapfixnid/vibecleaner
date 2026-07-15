import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.api.routes import settings as settings_route
from backend.core.config import AppConfig

def make_translation_service():
    return SimpleNamespace(system_prompt="", reload=lambda: None)

class SettingsUiLanguageTest(unittest.TestCase):
    def test_get_settings_includes_ui_language(self):
        cfg = AppConfig(ui_language="ko")

        payload = settings_route.get_settings_payload(cfg, make_translation_service())

        self.assertEqual(payload["ui_language"], "ko")

    def test_get_settings_includes_processing_options(self):
        cfg = AppConfig(
            detect_model="Small (INT8)",
            ocr_engine="ppocr",
            inpaint_engine="opencv",
            ocr_crop_scale=1.25,
            text_direction_override="horizontal",
            adaptive_binarization=False,
            adaptive_binarization_strength=3.0,
        )

        payload = settings_route.get_settings_payload(cfg, make_translation_service())

        self.assertEqual(payload["detect_model"], "Small (INT8)")
        self.assertEqual(payload["ocr_engine"], "ppocr")
        self.assertEqual(payload["inpaint_engine"], "opencv")
        self.assertEqual(payload["ocr_crop_scale"], 1.25)
        self.assertEqual(payload["text_direction_override"], "horizontal")
        self.assertFalse(payload["adaptive_binarization"])
        self.assertEqual(payload["adaptive_binarization_strength"], 3.0)

    def test_update_settings_persists_ui_language(self):
        cfg = AppConfig()
        translation_service = make_translation_service()
        current = settings_route.get_settings_payload(cfg, translation_service)
        updated = {
            **current,
            "ui_language": "ko",
            "translation_api_key": "",
            "translation_api_key_configured": True,
        }
        schema = settings_route.SettingsSchema(**updated)

        with (
            patch.object(cfg, "save", return_value=True),
            patch.object(translation_service, "reload"),
        ):
            response = settings_route.update_settings_payload(schema, cfg, translation_service)

        self.assertEqual(cfg.ui_language, "ko")
        self.assertEqual(response["ui_language"], "ko")

    def test_update_settings_persists_processing_options(self):
        cfg = AppConfig()
        translation_service = make_translation_service()
        current = settings_route.get_settings_payload(cfg, translation_service)
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
            patch.object(cfg, "save", return_value=True),
            patch.object(translation_service, "reload"),
        ):
            response = settings_route.update_settings_payload(schema, cfg, translation_service)

        self.assertEqual(cfg.detect_model, "Small (INT8)")
        self.assertEqual(cfg.ocr_engine, "manga_ocr")
        self.assertEqual(cfg.inpaint_engine, "opencv")
        self.assertEqual(cfg.ocr_crop_scale, 1.75)
        self.assertEqual(cfg.text_direction_override, "vertical")
        self.assertTrue(cfg.adaptive_binarization)
        self.assertEqual(cfg.adaptive_binarization_strength, 2.75)
        self.assertEqual(response["ocr_engine"], "manga_ocr")
        self.assertEqual(response["inpaint_engine"], "opencv")

if __name__ == "__main__":
    unittest.main()
