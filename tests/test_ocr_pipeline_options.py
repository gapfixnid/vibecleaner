import unittest
from unittest.mock import patch

import numpy as np

from backend.core.config import AppConfig
from backend.engines.ocr.ppocr import engine as ppocr_module
from backend.engines.ocr.ppocr.engine import PPOCRv6Engine
from backend.engines.ocr.base import OCREngineNotReadyError
from backend.engines.ocr.ppocr.preprocessing import apply_adaptive_binarization, crop_text_line
from backend.engines.ocr.local import LocalOCR
from backend.engines.common.textblock import TextBlock

class FakePPOCREngine:
    calls = []

    def initialize(self, lang="ch", device="cpu", model_name="ppocr-v6-medium"):
        self.lang = lang
        self.device = device
        self.model_name = model_name

    def process_image(self, image, blocks, **kwargs):
        self.calls.append(kwargs)
        for block in blocks:
            block.text = f"ppocr:{self.lang}"
        return blocks

class OcrPipelineOptionsTests(unittest.TestCase):
    def test_ppocr_reports_model_not_ready_instead_of_returning_input(self):
        engine = PPOCRv6Engine()
        block = TextBlock([0, 0, 20, 20])

        with self.assertRaises(OCREngineNotReadyError) as raised:
            engine.process_image(np.zeros((30, 30, 3), dtype=np.uint8), [block])

        self.assertEqual(raised.exception.code, "OCR_MODEL_NOT_READY")

    def test_local_ocr_uses_explicit_engine_without_global_config(self):
        block = TextBlock([1, 1, 10, 10])
        image = np.zeros((16, 16, 3), dtype=np.uint8)

        with (
            patch("backend.engines.ocr.local.PPOCRv6Engine", FakePPOCREngine),
        ):
            LocalOCR(lang="Japanese").recognize_text(image, [block], engine="ppocr")

        self.assertEqual(block.text, "ppocr:ch")

    def test_local_ocr_passes_gpu_device_when_cuda_is_available(self):
        block = TextBlock([1, 1, 10, 10])
        image = np.zeros((16, 16, 3), dtype=np.uint8)

        class GpuSettings:
            def is_gpu_enabled(self):
                return True

        with (
            patch("backend.engines.ocr.local.PPOCRv6Engine", FakePPOCREngine),
        ):
            ocr = LocalOCR(lang="English")
            ocr.settings = GpuSettings()
            ocr.recognize_text(image, [block], engine="ppocr")

        self.assertEqual(ocr.ppocr_engines[("ppocr-v6-medium", "en")].device, "cuda")

    def test_legacy_manga_setting_routes_to_ppocr(self):
        block = TextBlock([1, 1, 10, 10])
        image = np.zeros((16, 16, 3), dtype=np.uint8)

        class GpuSettings:
            def is_gpu_enabled(self):
                return True

        with patch("backend.engines.ocr.local.PPOCRv6Engine", FakePPOCREngine):
            ocr = LocalOCR(lang="Japanese")
            ocr.settings = GpuSettings()
            ocr.recognize_text(image, [block], engine="manga_ocr")

        self.assertEqual(ocr.ppocr_engines[("ppocr-v6-medium", "ch")].device, "cuda")
        self.assertEqual(block.text, "ppocr:ch")

    def test_forced_ppocr_engine_overrides_japanese_auto_engine(self):
        block = TextBlock([1, 1, 10, 10])
        image = np.zeros((16, 16, 3), dtype=np.uint8)

        with (
            patch("backend.engines.ocr.local.PPOCRv6Engine", FakePPOCREngine),
        ):
            LocalOCR(lang="Japanese").recognize_text(image, [block], engine="ppocr")

        self.assertEqual(block.text, "ppocr:ch")

    def test_fast_ocr_profile_uses_ppocr_even_for_japanese(self):
        block = TextBlock([1, 1, 10, 10])
        image = np.zeros((16, 16, 3), dtype=np.uint8)

        with (
            patch("backend.engines.ocr.local.PPOCRv6Engine", FakePPOCREngine),
        ):
            LocalOCR(lang="Japanese").recognize_text(image, [block], engine="fast")

        self.assertEqual(block.text, "ppocr:ch")

    def test_local_ocr_uses_selected_small_model(self):
        block = TextBlock([1, 1, 10, 10])
        image = np.zeros((16, 16, 3), dtype=np.uint8)

        with patch("backend.engines.ocr.local.PPOCRv6Engine", FakePPOCREngine):
            ocr = LocalOCR(lang="Japanese")
            ocr.recognize_text(image, [block], engine="ppocr", model="ppocr-v6-small")

        self.assertIn(("ppocr-v6-small", "ch"), ocr.ppocr_engines)
        self.assertEqual(ocr.ppocr_engines[("ppocr-v6-small", "ch")].model_name, "ppocr-v6-small")

    def test_local_ocr_passes_explicit_crop_options_to_ppocr(self):
        block = TextBlock([1, 1, 10, 10])
        image = np.zeros((16, 16, 3), dtype=np.uint8)
        FakePPOCREngine.calls = []

        with (
            patch("backend.engines.ocr.local.PPOCRv6Engine", FakePPOCREngine),
        ):
            LocalOCR(lang="Japanese").recognize_text(
                image,
                [block],
                engine="ppocr",
                padding=13,
                crop_scale=2.25,
                adaptive_binarization=False,
                adaptive_binarization_strength=3.5,
            )

        self.assertEqual(FakePPOCREngine.calls[0]["padding"], 13)
        self.assertEqual(FakePPOCREngine.calls[0]["crop_scale"], 2.25)
        self.assertIs(FakePPOCREngine.calls[0]["adaptive_binarization"], False)
        self.assertEqual(FakePPOCREngine.calls[0]["adaptive_binarization_strength"], 3.5)

    def test_ppocr_crop_line_uses_explicit_options_without_global_config(self):
        image = np.zeros((80, 80, 3), dtype=np.uint8)

        crop = ppocr_module._crop_line(
            image,
            [10, 10, 50, 50],
            padding=2,
            crop_scale=1.0,
            adaptive_binarization=False,
        )

        self.assertEqual(crop.shape[:2], (44, 44))

    def test_diagonal_quad_is_rectified_to_horizontal_crop(self):
        image = np.full((120, 120, 3), 255, dtype=np.uint8)
        quad = np.array([[15, 35], [95, 65], [89, 81], [9, 51]], dtype=np.float32)

        crop = crop_text_line(
            image,
            quad,
            padding=0,
            crop_scale=1.0,
            adaptive_binarization=False,
        )

        self.assertIsNotNone(crop)
        self.assertGreater(crop.shape[1], crop.shape[0] * 3)

    def test_ppocr_v6_uses_each_oriented_line_and_joins_japanese_text(self):
        block = TextBlock(
            [5, 5, 110, 110],
            lines=[
                np.array([[10, 20], [90, 45], [86, 57], [6, 32]]),
                np.array([[18, 48], [98, 73], [94, 85], [14, 60]]),
            ],
            source_lang="Japanese",
        )
        engine = PPOCRv6Engine()
        engine.rec_sess = object()
        engine.decoder = object()
        engine.source_language = "Japanese"

        with patch.object(engine, "_rec_infer", return_value=(["斜め", "台詞"], [0.98, 0.97])):
            engine.process_image(
                np.full((120, 120, 3), 255, dtype=np.uint8),
                [block],
                padding=0,
                crop_scale=1.0,
                adaptive_binarization=False,
            )

        self.assertEqual(block.text, "斜め台詞")
        self.assertEqual(block.texts, ["斜め", "台詞"])
        self.assertAlmostEqual(block.ocr_confidence, 0.975)

    def test_adaptive_binarization_strength_controls_clahe_clip_limit(self):
        cfg = AppConfig(adaptive_binarization_strength=3.25)
        crop = np.full((12, 12, 3), 128, dtype=np.uint8)

        with (
            patch("backend.engines.ocr.ppocr.preprocessing.cv2.createCLAHE") as create_clahe,
            patch("backend.engines.ocr.ppocr.preprocessing.cv2.adaptiveThreshold", return_value=np.zeros((12, 12), dtype=np.uint8)),
            patch("backend.engines.ocr.ppocr.preprocessing.cv2.cvtColor", side_effect=lambda image, *_args: image[:, :, 0] if image.ndim == 3 else np.dstack([image] * 3)),
        ):
            create_clahe.return_value.apply.side_effect = lambda gray: gray
            apply_adaptive_binarization(crop, strength=cfg.adaptive_binarization_strength)

        create_clahe.assert_called_once_with(clipLimit=3.25, tileGridSize=(8, 8))

    def test_ppocr_bboxes_use_y_coordinates_for_y2(self):
        engine = PPOCRv6Engine()
        engine.rec_sess = object()
        engine.decoder = object()
        block = TextBlock([0, 0, 100, 100])
        quad = np.array(
            [
                [10, 20],
                [40, 20],
                [40, 80],
                [10, 80],
            ],
            dtype=np.float32,
        )

        with (
            patch.object(engine, "_det_infer", return_value=([quad], [0.99])),
            patch.object(engine, "_rec_infer", return_value=(["hello"], [0.95])),
            patch.object(ppocr_module, "lists_to_blk_list", return_value=[block]) as to_blocks,
        ):
            engine.process_image(np.zeros((100, 100, 3), dtype=np.uint8), [block])

        self.assertEqual(to_blocks.call_args.args[1], [(10, 20, 40, 80)])

if __name__ == "__main__":
    unittest.main()
