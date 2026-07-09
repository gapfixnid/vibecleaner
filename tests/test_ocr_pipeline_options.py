import unittest
from unittest.mock import patch

import numpy as np

from backend.core.config import AppConfig
from backend.engines.ocr.ppocr import engine as ppocr_module
from backend.engines.ocr.ppocr.engine import PPOCRv5Engine
from backend.engines.ocr.ppocr.preprocessing import apply_adaptive_binarization
from backend.engines.ocr.local import LocalOCR
from backend.engines.common.textblock import TextBlock

class FakeMangaEngine:
    calls = []

    def initialize(self):
        pass

    def process_image(self, image, blocks, **kwargs):
        self.calls.append(kwargs)
        for block in blocks:
            block.text = "manga"
        return blocks

class FakePPOCREngine:
    calls = []

    def initialize(self, lang="ch"):
        self.lang = lang

    def process_image(self, image, blocks, **kwargs):
        self.calls.append(kwargs)
        for block in blocks:
            block.text = f"ppocr:{self.lang}"
        return blocks

class OcrPipelineOptionsTests(unittest.TestCase):
    def test_local_ocr_uses_explicit_engine_without_global_config(self):
        block = TextBlock([1, 1, 10, 10])
        image = np.zeros((16, 16, 3), dtype=np.uint8)

        with (
            patch("engines.ocr.local.MangaOCRMobileONNXEngine", FakeMangaEngine),
            patch("engines.ocr.local.PPOCRv5Engine", FakePPOCREngine),
        ):
            LocalOCR(lang="Japanese").recognize_text(image, [block], engine="ppocr")

        self.assertEqual(block.text, "ppocr:ch")

    def test_forced_ppocr_engine_overrides_japanese_auto_engine(self):
        block = TextBlock([1, 1, 10, 10])
        image = np.zeros((16, 16, 3), dtype=np.uint8)

        with (
            patch("engines.ocr.local.MangaOCRMobileONNXEngine", FakeMangaEngine),
            patch("engines.ocr.local.PPOCRv5Engine", FakePPOCREngine),
        ):
            LocalOCR(lang="Japanese").recognize_text(image, [block], engine="ppocr")

        self.assertEqual(block.text, "ppocr:ch")

    def test_fast_ocr_profile_uses_ppocr_even_for_japanese(self):
        block = TextBlock([1, 1, 10, 10])
        image = np.zeros((16, 16, 3), dtype=np.uint8)

        with (
            patch("engines.ocr.local.MangaOCRMobileONNXEngine", FakeMangaEngine),
            patch("engines.ocr.local.PPOCRv5Engine", FakePPOCREngine),
        ):
            LocalOCR(lang="Japanese").recognize_text(image, [block], engine="fast")

        self.assertEqual(block.text, "ppocr:ch")

    def test_local_ocr_passes_explicit_crop_options_to_ppocr(self):
        block = TextBlock([1, 1, 10, 10])
        image = np.zeros((16, 16, 3), dtype=np.uint8)
        FakePPOCREngine.calls = []

        with (
            patch("engines.ocr.local.MangaOCRMobileONNXEngine", FakeMangaEngine),
            patch("engines.ocr.local.PPOCRv5Engine", FakePPOCREngine),
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

    def test_adaptive_binarization_strength_controls_clahe_clip_limit(self):
        cfg = AppConfig(adaptive_binarization_strength=3.25)
        crop = np.full((12, 12, 3), 128, dtype=np.uint8)

        with (
            patch("engines.ocr.ppocr.preprocessing.cv2.createCLAHE") as create_clahe,
            patch("engines.ocr.ppocr.preprocessing.cv2.adaptiveThreshold", return_value=np.zeros((12, 12), dtype=np.uint8)),
            patch("engines.ocr.ppocr.preprocessing.cv2.cvtColor", side_effect=lambda image, *_args: image[:, :, 0] if image.ndim == 3 else np.dstack([image] * 3)),
        ):
            create_clahe.return_value.apply.side_effect = lambda gray: gray
            apply_adaptive_binarization(crop, strength=cfg.adaptive_binarization_strength)

        create_clahe.assert_called_once_with(clipLimit=3.25, tileGridSize=(8, 8))

    def test_ppocr_bboxes_use_y_coordinates_for_y2(self):
        engine = PPOCRv5Engine()
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
