import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from backend.core.models import Rect

import backend.api.use_cases.bubbles as bubble_service
from backend.core.models import MangaPage, TextBubble
from backend.core.state.project_state import ProjectState

class FakeRenderService:
    def __init__(self, layout):
        self.layout = layout

    def get_layout_for_bubble(self, *args, **kwargs):
        return self.layout

class BubbleServiceTests(unittest.TestCase):
    def setUp(self):
        self.state = ProjectState()

    def tearDown(self):
        pass

    def test_get_bubbles_response_exposes_text_and_layout_boxes(self):
        page = MangaPage(
            file_path="sample.png",
            cv_image=np.zeros((64, 64, 3), dtype=np.uint8),
            bubbles=[
                TextBubble(
                    id=1,
                    box=Rect(1, 2, 30, 40),
                    text_box=Rect(3, 4, 20, 22),
                    layout_box=Rect(5, 6, 16, 18),
                    text="hello",
                    translated="안녕",
                    font_size=14,
                )
            ],
        )
        page.page_id = "page_a"
        with self.state.lock:
            self.state.pages = [page]
            self.state.current_page_idx = 0

        fake_font = SimpleNamespace(pointSizeF=lambda: 14.0, family=lambda: "Resolved Font")
        fake_layout = SimpleNamespace(font=fake_font, line_layouts=[])
        response = bubble_service.get_bubbles_response(self.state, "page_a", FakeRenderService(fake_layout))

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
                    box=Rect(1, 2, 30, 40),
                    text="hello",
                    translated="안녕",
                    font_family="",
                    font_size=0,
                )
            ],
        )
        page.page_id = "page_a"
        with self.state.lock:
            self.state.pages = [page]
            self.state.current_page_idx = 0

        fake_font = SimpleNamespace(pixelSize=lambda: 17, family=lambda: "Resolved Font")
        fake_layout = SimpleNamespace(font=fake_font, line_layouts=[])
        response = bubble_service.get_bubbles_response(self.state, "page_a", FakeRenderService(fake_layout))

        bubble = response["bubbles"][0]
        self.assertEqual(bubble["font_family"], "")
        self.assertEqual(bubble["computed_font_family"], "Resolved Font")
        self.assertEqual(bubble["computed_font_size"], 17)
        self.assertEqual(bubble["font_mode"], "auto")
        self.assertIsNone(bubble["requested_font_size"])

    def test_get_bubbles_response_exposes_fixed_font_contract(self):
        page = MangaPage(
            file_path="sample.png",
            cv_image=np.zeros((64, 64, 3), dtype=np.uint8),
            bubbles=[
                TextBubble(
                    id=1,
                    box=Rect(1, 2, 30, 40),
                    translated="안녕",
                    font_size=22,
                )
            ],
        )
        page.page_id = "page_a"
        with self.state.lock:
            self.state.pages = [page]
            self.state.current_page_idx = 0

        fake_font = SimpleNamespace(pixelSize=lambda: 22, family=lambda: "Resolved Font")
        fake_layout = SimpleNamespace(font=fake_font, line_layouts=[], is_overflow=False)
        response = bubble_service.get_bubbles_response(self.state, "page_a", FakeRenderService(fake_layout))

        bubble = response["bubbles"][0]
        self.assertEqual(bubble["font_mode"], "fixed")
        self.assertEqual(bubble["requested_font_size"], 22)
        self.assertEqual(bubble["computed_font_size"], 22)

    def test_get_bubbles_response_marks_layout_overflow_from_render_result(self):
        page = MangaPage(
            file_path="sample.png",
            cv_image=np.zeros((64, 64, 3), dtype=np.uint8),
            bubbles=[
                TextBubble(
                    id=1,
                    box=Rect(1, 2, 30, 40),
                    text="hello",
                    translated="안녕",
                    font_family="",
                    font_size=0,
                )
            ],
        )
        page.page_id = "page_a"
        with self.state.lock:
            self.state.pages = [page]
            self.state.current_page_idx = 0

        fake_font = SimpleNamespace(pointSizeF=lambda: 8.0, family=lambda: "Resolved Font")
        fake_layout = SimpleNamespace(font=fake_font, line_layouts=[], is_overflow=True, reached_min_font=True)
        response = bubble_service.get_bubbles_response(self.state, "page_a", FakeRenderService(fake_layout))

        bubble = response["bubbles"][0]
        self.assertEqual(bubble["status"], "layout_overflow")
        self.assertIn("layout overflow", bubble["problems"])
        self.assertTrue(bubble["layout_overflow"])

    def test_get_bubbles_response_does_not_load_image_when_page_has_no_bubbles(self):
        page = MangaPage(file_path="missing.png", cv_image=None, bubbles=[])
        page.page_id = "page_a"
        page._loaded = False
        with self.state.lock:
            self.state.pages = [page]
            self.state.current_page_idx = 0

        with patch.object(bubble_service, "load_cv_image") as load_image:
            response = bubble_service.get_bubbles_response(self.state, "page_a", FakeRenderService(None))

        self.assertEqual(response, {"bubbles": []})
        load_image.assert_not_called()

if __name__ == "__main__":
    unittest.main()
