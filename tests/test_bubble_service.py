import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from PySide6.QtCore import QRectF

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import services.bubble_service as bubble_service
from app.models import MangaPage, TextBubble


class BubbleServiceTests(unittest.TestCase):
    def setUp(self):
        self.original_pages = list(bubble_service.state.pages)
        self.original_current_page_idx = bubble_service.state.current_page_idx

    def tearDown(self):
        with bubble_service.state.lock:
            bubble_service.state.pages = self.original_pages
            bubble_service.state.current_page_idx = self.original_current_page_idx

    def test_get_bubbles_response_exposes_text_and_layout_boxes(self):
        page = MangaPage(
            file_path="sample.png",
            cv_image=np.zeros((64, 64, 3), dtype=np.uint8),
            bubbles=[
                TextBubble(
                    id=1,
                    box=QRectF(1, 2, 30, 40),
                    text_box=QRectF(3, 4, 20, 22),
                    layout_box=QRectF(5, 6, 16, 18),
                    text="hello",
                    translated="안녕",
                    font_size=14,
                )
            ],
        )
        page.page_id = "page_a"
        with bubble_service.state.lock:
            bubble_service.state.pages = [page]
            bubble_service.state.current_page_idx = 0

        fake_font = SimpleNamespace(pointSizeF=lambda: 14.0, family=lambda: "Resolved Font")
        fake_layout = SimpleNamespace(font=fake_font, line_layouts=[])
        with patch.object(
            bubble_service.render_service,
            "get_layout_for_bubble",
            return_value=fake_layout,
        ):
            response = bubble_service.get_bubbles_response("page_a")

        bubble = response["bubbles"][0]
        self.assertEqual(bubble["text_box"], {"x": 3.0, "y": 4.0, "width": 20.0, "height": 22.0})
        self.assertEqual(bubble["layout_box"], {"x": 5.0, "y": 6.0, "width": 16.0, "height": 18.0})

    def test_get_bubbles_response_exposes_computed_font_family(self):
        page = MangaPage(
            file_path="sample.png",
            cv_image=np.zeros((64, 64, 3), dtype=np.uint8),
            bubbles=[
                TextBubble(
                    id=1,
                    box=QRectF(1, 2, 30, 40),
                    text="hello",
                    translated="안녕",
                    font_family="",
                    font_size=0,
                )
            ],
        )
        page.page_id = "page_a"
        with bubble_service.state.lock:
            bubble_service.state.pages = [page]
            bubble_service.state.current_page_idx = 0

        fake_font = SimpleNamespace(pointSizeF=lambda: 17.0, family=lambda: "Resolved Font")
        fake_layout = SimpleNamespace(font=fake_font, line_layouts=[])
        with patch.object(
            bubble_service.render_service,
            "get_layout_for_bubble",
            return_value=fake_layout,
        ):
            response = bubble_service.get_bubbles_response("page_a")

        bubble = response["bubbles"][0]
        self.assertEqual(bubble["font_family"], "")
        self.assertEqual(bubble["computed_font_family"], "Resolved Font")
        self.assertEqual(bubble["computed_font_size"], 17)


if __name__ == "__main__":
    unittest.main()
