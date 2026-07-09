import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from core.config import AppConfig
from infrastructure.downloads import ModelID
from infrastructure.downloads.requirements import get_required_model_ids, get_model_status
from api.routes import settings as settings_route
from download_models import get_model_ids


class ModelRequirementsTests(unittest.TestCase):
    def test_balanced_japanese_uses_fp32_detection_manga_ocr_and_lama(self):
        cfg = AppConfig(
            detect_model="High Precision (FP32)",
            source_language="Japanese",
            ocr_engine="balanced",
            inpaint_engine="lama",
        )

        self.assertEqual(
            get_required_model_ids(cfg),
            [
                ModelID.RTDETR_V2_ONNX,
                ModelID.MANGA_OCR_MOBILE_ONNX,
                ModelID.LAMA_ONNX,
            ],
        )

    def test_fast_japanese_uses_int8_detection_ppocr_chinese_recognition_and_no_inpaint_model(self):
        cfg = AppConfig(
            detect_model="Small (INT8)",
            source_language="Japanese",
            ocr_engine="fast",
            inpaint_engine="opencv",
        )

        self.assertEqual(
            get_required_model_ids(cfg),
            [
                ModelID.RTDETR_INT8_ONNX,
                ModelID.PPOCR_V5_DET_MOBILE,
                ModelID.PPOCR_V5_REC_MOBILE,
            ],
        )

    def test_balanced_korean_uses_ppocr_korean_recognition(self):
        cfg = AppConfig(
            detect_model="High Precision (FP32)",
            source_language="Korean",
            ocr_engine="balanced",
            inpaint_engine="lama",
        )

        self.assertEqual(
            get_required_model_ids(cfg),
            [
                ModelID.RTDETR_V2_ONNX,
                ModelID.PPOCR_V5_DET_MOBILE,
                ModelID.PPOCR_V5_REC_KOREAN_MOBILE,
                ModelID.LAMA_ONNX,
            ],
        )

    def test_status_marks_missing_models_without_downloading(self):
        cfg = AppConfig(
            detect_model="Small (INT8)",
            source_language="English",
            ocr_engine="fast",
            inpaint_engine="opencv",
        )

        with patch(
            "infrastructure.downloads.requirements.ModelDownloader.is_downloaded",
            side_effect=lambda model_id: model_id == ModelID.RTDETR_INT8_ONNX,
        ) as is_downloaded:
            status = get_model_status(cfg)

        self.assertFalse(status["all_ready"])
        self.assertEqual(status["missing_count"], 2)
        self.assertEqual(
            [item["id"] for item in status["missing"]],
            [ModelID.PPOCR_V5_DET_MOBILE.value, ModelID.PPOCR_V5_REC_EN_MOBILE.value],
        )
        self.assertEqual(is_downloaded.call_count, 3)

    def test_download_script_current_profile_uses_settings_requirements(self):
        cfg = AppConfig(
            detect_model="Small (INT8)",
            source_language="Korean",
            ocr_engine="balanced",
            inpaint_engine="opencv",
        )

        self.assertEqual(
            get_model_ids("current", cfg),
            [
                ModelID.RTDETR_INT8_ONNX,
                ModelID.PPOCR_V5_DET_MOBILE,
                ModelID.PPOCR_V5_REC_KOREAN_MOBILE,
            ],
        )

    def test_model_status_route_uses_current_config(self):
        cfg = AppConfig(
            detect_model="High Precision (FP32)",
            source_language="Japanese",
            ocr_engine="balanced",
            inpaint_engine="opencv",
        )

        with (
            patch("infrastructure.downloads.requirements.ModelDownloader.is_downloaded", return_value=True),
        ):
            status = settings_route.get_models_status_for_config(cfg)

        self.assertTrue(status["all_ready"])
        self.assertEqual(
            [item["id"] for item in status["required"]],
            [ModelID.RTDETR_V2_ONNX.value, ModelID.MANGA_OCR_MOBILE_ONNX.value],
        )


if __name__ == "__main__":
    unittest.main()
