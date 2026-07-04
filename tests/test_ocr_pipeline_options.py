import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from modules.config import AppConfig
from modules.ocr.ppocr import engine as ppocr_module
from modules.ocr.ppocr.engine import PPOCRv5Engine
from modules.ocr_wrapper import LocalOCR
from modules.utils.textblock import TextBlock


class FakeMangaEngine:
    def initialize(self):
        pass

    def process_image(self, image, blocks):
        for block in blocks:
            block.text = "manga"
        return blocks


class FakePPOCREngine:
    def initialize(self, lang="ch"):
        self.lang = lang

    def process_image(self, image, blocks):
        for block in blocks:
            block.text = f"ppocr:{self.lang}"
        return blocks


class OcrPipelineOptionsTests(unittest.TestCase):
    def test_forced_ppocr_engine_overrides_japanese_auto_engine(self):
        cfg = AppConfig(ocr_engine="ppocr")
        block = TextBlock([1, 1, 10, 10])
        image = np.zeros((16, 16, 3), dtype=np.uint8)

        with (
            patch("modules.config.config", cfg),
            patch("modules.ocr_wrapper.MangaOCRMobileONNXEngine", FakeMangaEngine),
            patch("modules.ocr_wrapper.PPOCRv5Engine", FakePPOCREngine),
        ):
            LocalOCR(lang="Japanese").recognize_text(image, [block])

        self.assertEqual(block.text, "ppocr:ch")

    def test_adaptive_binarization_strength_controls_clahe_clip_limit(self):
        cfg = AppConfig(adaptive_binarization_strength=3.25)
        crop = np.full((12, 12, 3), 128, dtype=np.uint8)

        with (
            patch("modules.config.config", cfg),
            patch("modules.config.cv2.createCLAHE") as create_clahe,
            patch("modules.config.cv2.adaptiveThreshold", return_value=np.zeros((12, 12), dtype=np.uint8)),
            patch("modules.config.cv2.cvtColor", side_effect=lambda image, *_args: image[:, :, 0] if image.ndim == 3 else np.dstack([image] * 3)),
        ):
            create_clahe.return_value.apply.side_effect = lambda gray: gray
            cfg.apply_adaptive_binarization(crop)

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
