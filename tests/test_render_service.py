import unittest
from types import SimpleNamespace

import numpy as np
from backend.core.models import Rect

from backend.core.models import TextBubble
from backend.engines.rendering.service import RenderService

def _rect_from_qrectf(rect) -> Rect:
    """The service hands the renderer Qt geometry; record it as a core Rect."""
    return Rect(rect.x(), rect.y(), rect.width(), rect.height())

class FakeRenderer:
    def __init__(self):
        self.font_rect = None
        self.layout_rect = None
        self.font_family = "not-called"
        self.mask_rect = None
        self.mask_shape = None
        self.vertical_center_y = None
        self.vertical_bounds = None
        self.min_size = None
        self.max_size = None
        self.fixed_font_size = None
        self.fixed_mask = None

    def find_optimal_font_size(self, text, rect, font_family=None, min_size=None, max_size=None):
        self.font_rect = _rect_from_qrectf(rect)
        self.font_family = font_family
        self.min_size = min_size
        self.max_size = max_size
        return SimpleNamespace(pointSizeF=lambda: 18.0), [text], rect.width()

    def layout_lines_in_rect(self, lines, rect, font, render_width, alignment="center"):
        self.layout_rect = _rect_from_qrectf(rect)
        return SimpleNamespace(
            font=font,
            line_layouts=[],
        )

    def find_optimal_font_size_for_mask(self, text, rect, mask, font_family=None, min_size=None, max_size=None):
        self.mask_rect = _rect_from_qrectf(rect)
        self.mask_shape = mask.shape
        self.font_family = font_family
        self.min_size = min_size
        self.max_size = max_size
        return SimpleNamespace(
            font=SimpleNamespace(pointSizeF=lambda: 18.0, family=lambda: "Resolved Font"),
            line_layouts=[],
        )

    def layout_text_at_fixed_size(
        self,
        text,
        rect,
        font_size,
        mask=None,
        font_family=None,
        alignment="center",
    ):
        self.fixed_font_size = font_size
        self.fixed_mask = mask
        self.font_family = font_family
        return SimpleNamespace(
            font=SimpleNamespace(pixelSize=lambda: font_size, family=lambda: "Resolved Font"),
            line_layouts=[],
            is_overflow=False,
            reached_min_font=False,
        )

    def make_ellipse_mask(self, width, height, inset=0):
        return np.ones((height, width), dtype=np.uint8)

    def center_layout_vertically(self, layout, target_center_y, bounds):
        self.vertical_center_y = target_center_y
        self.vertical_bounds = _rect_from_qrectf(bounds)
        return layout

class RenderServiceTests(unittest.TestCase):
    def test_render_service_passes_explicit_font_size_options_to_renderer(self):
        renderer = FakeRenderer()
        service = RenderService(renderer=renderer, config=SimpleNamespace(min_font_size=9.0, max_font_size=27.0))
        bubble = TextBubble(
            id=1,
            box=Rect(0, 0, 100, 80),
            text_box=Rect(24, 18, 52, 36),
            layout_box=Rect(20, 12, 40, 24),
            text="hello",
        )

        service.get_layout_for_bubble("translated", bubble, image=None, font_family="Test")

        self.assertEqual(renderer.min_size, 9.0)
        self.assertEqual(renderer.max_size, 27.0)

    def test_text_bubble_uses_full_bubble_box_for_mask_layout(self):
        renderer = FakeRenderer()
        service = RenderService(renderer=renderer)
        bubble = TextBubble(
            id=1,
            box=Rect(0, 0, 100, 80),
            text_box=Rect(24, 18, 52, 36),
            layout_box=Rect(20, 12, 40, 24),
            text="hello",
            text_class="text_bubble",
        )

        service.get_layout_for_bubble("translated", bubble, image=None, font_family="Test")

        self.assertEqual(renderer.mask_rect, Rect(0, 0, 100, 80))
        self.assertEqual(renderer.mask_shape, (80, 100))
        self.assertEqual(renderer.vertical_center_y, 36.0)
        self.assertEqual(renderer.vertical_bounds, Rect(0, 0, 100, 80))

    def test_auto_font_selection_reaches_renderer_when_no_font_family_is_requested(self):
        renderer = FakeRenderer()
        service = RenderService(renderer=renderer)
        bubble = TextBubble(
            id=1,
            box=Rect(0, 0, 100, 80),
            layout_box=Rect(20, 12, 40, 24),
            text="hello",
        )

        service.get_layout_for_bubble("translated", bubble, image=None, font_family=None)

        self.assertIsNone(renderer.font_family)

    def test_fixed_font_size_reflows_without_running_auto_sizing(self):
        renderer = FakeRenderer()
        service = RenderService(renderer=renderer)
        bubble = TextBubble(
            id=1,
            box=Rect(0, 0, 100, 80),
            text="hello",
            text_class="text_free",
            font_size=24,
        )

        layout = service.get_layout_for_bubble("translated", bubble, image=None, font_family="Test")

        self.assertEqual(renderer.fixed_font_size, 24)
        self.assertIsNone(renderer.fixed_mask)
        self.assertEqual(layout.font.pixelSize(), 24)
        self.assertIsNone(renderer.font_rect)

if __name__ == "__main__":
    unittest.main()
