import unittest
import numpy as np

from backend.pipeline.analysis import bubbles as bubble_module
from backend.pipeline.analysis.bubbles import BubbleAnalysisService

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

    def test_same_parent_bubble_lines_are_grouped(self):
        service = BubbleAnalysisService()
        first = bubble_module.BubbleData(
            bubble_box=(10, 10, 90, 90), text_box=(30, 20, 60, 35),
            layout_box=(30, 20, 60, 35), text="첫 줄", direction="vertical",
        )
        second = bubble_module.BubbleData(
            bubble_box=(11, 11, 89, 89), text_box=(30, 45, 60, 60),
            layout_box=(30, 45, 60, 60), text="둘째 줄", direction="vertical",
        )

        grouped = service._group_into_bubbles(None, [first, second])

        assert len(grouped) == 1
        assert grouped[0].text == "첫 줄\n둘째 줄"
        assert grouped[0].text_box == (30, 20, 60, 60)

    def test_distinct_overlapping_bubbles_are_not_grouped(self):
        service = BubbleAnalysisService()
        first = bubble_module.BubbleData(
            bubble_box=(10, 10, 60, 60), text_box=(15, 15, 30, 30),
            layout_box=(15, 15, 30, 30), text="first",
        )
        second = bubble_module.BubbleData(
            bubble_box=(45, 45, 95, 95), text_box=(65, 65, 85, 85),
            layout_box=(65, 65, 85, 85), text="second",
        )

        grouped = service._group_into_bubbles(None, [first, second])

        assert len(grouped) == 2

if __name__ == "__main__":
    unittest.main()
