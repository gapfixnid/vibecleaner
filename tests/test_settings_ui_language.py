import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.api.routes import settings as settings_route
from backend.core.config import AppConfig
from fastapi import HTTPException

def make_translation_service():
    return SimpleNamespace(system_prompt="", reload=lambda: None)

class SettingsUiLanguageTest(unittest.TestCase):
    def test_new_install_defaults_to_aot_inpainting(self):
        self.assertEqual(AppConfig().inpaint_engine, "aot")

    def test_update_settings_rejects_unsupported_local_model(self):
        cfg = AppConfig()
        service = make_translation_service()
        payload = settings_route.get_settings_payload(cfg, service)
        schema = settings_route.SettingsSchema(**{
            **payload,
            "detect_model": "arbitrary-model.onnx",
        })

        with self.assertRaises(HTTPException) as raised:
            settings_route.update_settings_payload(schema, cfg, service)

        self.assertEqual(raised.exception.status_code, 422)

    def test_get_settings_includes_ui_language(self):
        cfg = AppConfig(ui_language="ko")

        payload = settings_route.get_settings_payload(cfg, make_translation_service())

        self.assertEqual(payload["ui_language"], "ko")

    def test_get_settings_includes_processing_options(self):
        cfg = AppConfig(
            detect_model="Small (INT8)",
            ocr_engine="ppocr",
            inpaint_engine="aot",
            ocr_crop_scale=1.25,
            text_direction_override="horizontal",
            adaptive_binarization=False,
            adaptive_binarization_strength=3.0,
            show_detection_overlay=True,
        )

        payload = settings_route.get_settings_payload(cfg, make_translation_service())

        self.assertEqual(payload["detect_model"], "Small (INT8)")
        self.assertEqual(payload["ocr_engine"], "ppocr")
        self.assertEqual(payload["inpaint_engine"], "aot")
        self.assertEqual(payload["ocr_crop_scale"], 1.25)
        self.assertEqual(payload["text_direction_override"], "horizontal")
        self.assertFalse(payload["adaptive_binarization"])
        self.assertEqual(payload["adaptive_binarization_strength"], 3.0)
        self.assertTrue(payload["show_detection_overlay"])

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
            "inpaint_engine": "aot",
            "ocr_crop_scale": 1.75,
            "text_direction_override": "vertical",
            "adaptive_binarization": True,
            "adaptive_binarization_strength": 2.75,
            "show_detection_overlay": True,
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
        self.assertEqual(cfg.ocr_engine, "ppocr")
        self.assertEqual(cfg.inpaint_engine, "aot")
        self.assertEqual(cfg.ocr_crop_scale, 1.75)
        self.assertEqual(cfg.text_direction_override, "vertical")
        self.assertTrue(cfg.adaptive_binarization)
        self.assertTrue(cfg.show_detection_overlay)
        self.assertEqual(cfg.adaptive_binarization_strength, 2.75)
        self.assertEqual(response["ocr_engine"], "ppocr")
        self.assertEqual(response["inpaint_engine"], "aot")

if __name__ == "__main__":
    unittest.main()
