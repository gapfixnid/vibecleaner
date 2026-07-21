import unittest
from unittest.mock import patch

import numpy as np

from backend.engines.inpainting.hybrid import HybridInpainter, build_oriented_target_mask, _polygon_is_slanted

class InpaintingEngineOptionsTests(unittest.TestCase):
    def test_only_rotated_polygons_enable_diagonal_mask_expansion(self):
        self.assertTrue(_polygon_is_slanted([[10, 20], [80, 45], [76, 58], [6, 33]]))
        self.assertFalse(_polygon_is_slanted([[10, 20], [80, 20], [80, 40], [10, 40]]))

    def test_oriented_target_mask_does_not_fill_axis_aligned_corners(self):
        mask = build_oriented_target_mask(
            [[[20, 8], [32, 20], [20, 32], [8, 20]]],
            origin_x=0,
            origin_y=0,
            width=40,
            height=40,
            margin=2,
        )

        self.assertIsNotNone(mask)
        assert mask is not None
        self.assertEqual(mask[20, 20], 255)
        self.assertEqual(mask[8, 8], 0)

    def test_inpainter_uses_explicit_options_without_global_config(self):
        image = np.full((24, 24, 3), 255, dtype=np.uint8)
        image[9:15, 9:15] = 0
        output_crop = np.full((20, 20, 3), 200, dtype=np.uint8)

        with (
            patch("backend.engines.inpainting.hybrid.cv2.inpaint", return_value=output_crop) as cv_inpaint,
            patch("backend.engines.inpainting.lama.LaMa") as lama_cls,
        ):
            result = HybridInpainter().inpaint(
                image,
                [[10, 10, 14, 14]],
                engine="opencv",
                mask_dilation=2,
                clip_to_bubble=False,
            )

        self.assertEqual(cv_inpaint.call_count, 1)
        lama_cls.assert_not_called()
        np.testing.assert_array_equal(result[2, 2], image[2, 2])
        np.testing.assert_array_equal(result[11, 11], output_crop[9, 9])

    def test_opencv_inpaint_profile_does_not_initialize_lama(self):
        image = np.full((24, 24, 3), 255, dtype=np.uint8)
        image[9:15, 9:15] = 0
        output_crop = np.full((20, 20, 3), 200, dtype=np.uint8)

        with (
            patch("backend.engines.inpainting.hybrid.cv2.inpaint", return_value=output_crop) as cv_inpaint,
            patch("backend.engines.inpainting.lama.LaMa") as lama_cls,
        ):
            result = HybridInpainter().inpaint(image, [[10, 10, 14, 14]], engine="opencv")

        self.assertEqual(cv_inpaint.call_count, 1)
        lama_cls.assert_not_called()
        np.testing.assert_array_equal(result[2, 2], image[2, 2])
        np.testing.assert_array_equal(result[11, 11], output_crop[9, 9])

    def test_legacy_high_precision_profile_uses_balanced_lama_engine(self):
        image = np.full((24, 24, 3), 255, dtype=np.uint8)
        image[9:15, 9:15] = 0
        output_crop = np.full((20, 20, 3), 180, dtype=np.uint8)

        class FakeLaMa:
            def __init__(self, *args, **kwargs):
                pass

            def __call__(self, crop, mask, config=None):
                return output_crop

        with (
            patch("backend.engines.inpainting.lama.LaMa", side_effect=FakeLaMa) as lama_cls,
            patch("backend.engines.inpainting.aot.AOT") as aot_cls,
        ):
            result = HybridInpainter().inpaint(image, [[10, 10, 14, 14]], engine="aot")

        aot_cls.assert_not_called()
        self.assertEqual(lama_cls.call_count, 1)
        np.testing.assert_array_equal(result[2, 2], image[2, 2])
        np.testing.assert_array_equal(result[11, 11], output_crop[9, 9])

if __name__ == "__main__":
    unittest.main()
