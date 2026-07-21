import unittest
from unittest.mock import patch

from backend.core.config import AppConfig
from backend.infrastructure.downloads import ModelID
from backend.infrastructure.downloads.requirements import get_required_model_ids, get_model_status
from backend.api.routes import settings as settings_route
from download_models import get_model_ids

class ModelRequirementsTests(unittest.TestCase):
    def test_legacy_balanced_japanese_uses_ppocr_v6_and_lama(self):
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
                ModelID.PPOCR_V6_DET_MEDIUM,
                ModelID.PPOCR_V6_REC_MEDIUM,
                ModelID.LAMA_ONNX,
            ],
        )

    def test_int8_japanese_with_aot_uses_supported_onnx_models(self):
        cfg = AppConfig(
            detect_model="Small (INT8)",
            source_language="Japanese",
            ocr_engine="fast",
            inpaint_engine="aot",
        )

        self.assertEqual(
            get_required_model_ids(cfg),
            [
                ModelID.RTDETR_INT8_ONNX,
                ModelID.PPOCR_V6_DET_MEDIUM,
                ModelID.PPOCR_V6_REC_MEDIUM,
                ModelID.AOT_ONNX,
            ],
        )

    def test_yolo_selection_uses_downloadable_yolo_model(self):
        cfg = AppConfig(
            detect_model="YOLOv8/11 ONNX",
            source_language="Japanese",
            ocr_model="ppocr-v6-medium",
            inpaint_engine="aot",
        )

        self.assertEqual(
            get_required_model_ids(cfg),
            [
                ModelID.YOLO_V8_ONNX,
                ModelID.PPOCR_V6_DET_MEDIUM,
                ModelID.PPOCR_V6_REC_MEDIUM,
                ModelID.AOT_ONNX,
            ],
        )

    def test_small_ocr_selection_uses_small_detection_and_recognition(self):
        cfg = AppConfig(
            detect_model="High Precision (FP32)",
            source_language="Japanese",
            ocr_model="ppocr-v6-small",
            inpaint_engine="aot",
        )

        self.assertEqual(
            get_required_model_ids(cfg),
            [
                ModelID.RTDETR_V2_ONNX,
                ModelID.PPOCR_V6_DET_SMALL,
                ModelID.PPOCR_V6_REC_SMALL,
                ModelID.AOT_ONNX,
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
                ModelID.PPOCR_V6_DET_MEDIUM,
                ModelID.PPOCR_V6_REC_MEDIUM,
                ModelID.LAMA_ONNX,
            ],
        )

    def test_legacy_manga_ocr_setting_uses_ppocr_v6(self):
        cfg = AppConfig(
            detect_model="High Precision (FP32)",
            source_language="Korean",
            ocr_engine="manga_ocr",
            inpaint_engine="aot",
        )

        self.assertEqual(
            get_required_model_ids(cfg),
            [ModelID.RTDETR_V2_ONNX, ModelID.PPOCR_V6_DET_MEDIUM, ModelID.PPOCR_V6_REC_MEDIUM, ModelID.AOT_ONNX],
        )

    def test_status_marks_missing_models_without_downloading(self):
        cfg = AppConfig(
            detect_model="Small (INT8)",
            source_language="English",
            ocr_engine="fast",
            inpaint_engine="aot",
        )

        with patch(
            "backend.infrastructure.downloads.requirements.ModelDownloader.is_downloaded",
            side_effect=lambda model_id: model_id == ModelID.RTDETR_INT8_ONNX,
        ) as is_downloaded:
            status = get_model_status(cfg)

        self.assertFalse(status["all_ready"])
        self.assertEqual(status["missing_count"], 3)
        self.assertEqual(
            [item["id"] for item in status["missing"]],
            [ModelID.PPOCR_V6_DET_MEDIUM.value, ModelID.PPOCR_V6_REC_MEDIUM.value, ModelID.AOT_ONNX.value],
        )
        self.assertEqual(is_downloaded.call_count, 4)

    def test_download_script_current_profile_uses_settings_requirements(self):
        cfg = AppConfig(
            detect_model="Small (INT8)",
            source_language="Korean",
            ocr_engine="balanced",
            inpaint_engine="aot",
        )

        self.assertEqual(
            get_model_ids("current", cfg),
            [
                ModelID.RTDETR_INT8_ONNX,
                ModelID.PPOCR_V6_DET_MEDIUM,
                ModelID.PPOCR_V6_REC_MEDIUM,
                ModelID.AOT_ONNX,
            ],
        )

    def test_model_status_route_uses_current_config(self):
        cfg = AppConfig(
            detect_model="High Precision (FP32)",
            source_language="Japanese",
            ocr_engine="balanced",
            inpaint_engine="aot",
        )

        with (
            patch("backend.infrastructure.downloads.requirements.ModelDownloader.is_downloaded", return_value=True),
        ):
            status = settings_route.get_models_status_for_config(cfg)

        self.assertTrue(status["all_ready"])
        self.assertEqual(
            [item["id"] for item in status["required"]],
            [ModelID.RTDETR_V2_ONNX.value, ModelID.PPOCR_V6_DET_MEDIUM.value, ModelID.PPOCR_V6_REC_MEDIUM.value, ModelID.AOT_ONNX.value],
        )

if __name__ == "__main__":
    unittest.main()
