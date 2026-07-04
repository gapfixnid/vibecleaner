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
from modules.inpainting_wrapper import HybridInpainter


class InpaintingEngineOptionsTests(unittest.TestCase):
    def test_opencv_inpaint_profile_does_not_initialize_lama(self):
        cfg = AppConfig(inpaint_engine="opencv")
        image = np.full((24, 24, 3), 255, dtype=np.uint8)
        image[9:15, 9:15] = 0
        output_crop = np.full((20, 20, 3), 200, dtype=np.uint8)

        with (
            patch("modules.inpainting_wrapper.config", cfg),
            patch("modules.inpainting_wrapper.cv2.inpaint", return_value=output_crop) as cv_inpaint,
            patch("modules.inpainting.lama.LaMa") as lama_cls,
        ):
            result = HybridInpainter().inpaint(image, [[10, 10, 14, 14]])

        self.assertEqual(cv_inpaint.call_count, 1)
        lama_cls.assert_not_called()
        np.testing.assert_array_equal(result[2:22, 2:22], output_crop)


if __name__ == "__main__":
    unittest.main()
