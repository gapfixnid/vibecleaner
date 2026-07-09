import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from core.models import Rect

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from core.models import TextBubble
from engines.rendering.service import RenderService


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
        self.min_size = None
        self.max_size = None

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

    def make_ellipse_mask(self, width, height, inset=0):
        return np.ones((height, width), dtype=np.uint8)


class RenderServiceTests(unittest.TestCase):
    def test_render_service_passes_explicit_font_size_options_to_renderer(self):
        renderer = FakeRenderer()
        service = RenderService(renderer=renderer, config=SimpleNamespace(min_font_size=9.0, max_font_size=27.0))
        bubble = TextBubble(
            id=1,
            box=Rect(0, 0, 100, 80),
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
            layout_box=Rect(20, 12, 40, 24),
            text="hello",
            text_class="text_bubble",
        )

        service.get_layout_for_bubble("translated", bubble, image=None, font_family="Test")

        self.assertEqual(renderer.mask_rect, Rect(0, 0, 100, 80))
        self.assertEqual(renderer.mask_shape, (80, 100))

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


if __name__ == "__main__":
    unittest.main()
