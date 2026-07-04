import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services import bubble_analysis_service as bubble_module
from services.bubble_analysis_service import BubbleAnalysisService


class BubbleAnalysisServiceTests(unittest.TestCase):
    def test_layout_box_uses_distance_transform_and_stays_inside_bubble(self):
        if not bubble_module.HAS_CV2:
            self.skipTest("OpenCV is required for distance-transform layout")

        image = np.zeros((100, 100, 3), dtype=np.uint8)
        image[20:80, 20:80] = 255

        service = BubbleAnalysisService(layout_padding_ratio=0.1)
        layout = service._calculate_layout_box(
            image,
            bubble_box=(20, 20, 80, 80),
            text_box=(44, 44, 56, 56),
            text_class="text_bubble",
        )

        x1, y1, x2, y2 = layout
        self.assertGreater(x2 - x1, 20)
        self.assertGreater(y2 - y1, 20)
        self.assertGreaterEqual(x1, 20)
        self.assertGreaterEqual(y1, 20)
        self.assertLessEqual(x2, 80)
        self.assertLessEqual(y2, 80)

    def test_korean_bubbles_sort_left_to_right_like_page_analysis(self):
        service = BubbleAnalysisService()
        left = bubble_module.BubbleData(
            bubble_box=(10, 10, 30, 30),
            text_box=(10, 10, 30, 30),
            layout_box=(10, 10, 30, 30),
            text="left",
        )
        right = bubble_module.BubbleData(
            bubble_box=(70, 10, 90, 30),
            text_box=(70, 10, 90, 30),
            layout_box=(70, 10, 90, 30),
            text="right",
        )

        reading_order = service._get_reading_order("Korean")
        sorted_bubbles = service._sort_by_reading_order([right, left], reading_order)

        self.assertEqual(reading_order, "LTR")
        self.assertEqual([bubble.text for bubble in sorted_bubbles], ["left", "right"])


if __name__ == "__main__":
    unittest.main()
