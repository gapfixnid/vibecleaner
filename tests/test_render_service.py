import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from backend.core.models import Rect

from backend.core.models import TextBubble
from backend.engines.rendering.service import RenderService
from backend.infrastructure.image.masks import (
    BubbleClipMaskResult,
)

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

    def find_optimal_font_size(
        self,
        text,
        rect,
        font_family=None,
        min_size=None,
        max_size=None,
        padding=None,
        margin=None,
        target_center_y=None,
    ):
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

    def find_optimal_font_size_for_mask(
        self,
        text,
        rect,
        mask,
        font_family=None,
        min_size=None,
        max_size=None,
        alignment="center",
        padding=None,
        margin=None,
        target_center_y=None,
    ):
        self.mask_rect = _rect_from_qrectf(rect)
        self.mask_shape = mask.shape
        self.font_family = font_family
        self.min_size = min_size
        self.max_size = max_size
        self.vertical_center_y = target_center_y
        return SimpleNamespace(
            font=SimpleNamespace(pointSizeF=lambda: 18.0, family=lambda: "Resolved Font"),
            line_layouts=[],
        )

    def find_optimal_layout_in_rect(
        self,
        text,
        rect,
        font_family=None,
        min_size=None,
        max_size=None,
        alignment="center",
        padding=None,
        margin=None,
    ):
        font, lines, render_width = self.find_optimal_font_size(
            text,
            rect,
            font_family=font_family,
            min_size=min_size,
            max_size=max_size,
            padding=padding,
            margin=margin,
        )
        return self.layout_lines_in_rect(lines, rect, font, render_width, alignment=alignment)

    def layout_text_at_fixed_size(
        self,
        text,
        rect,
        font_size,
        mask=None,
        font_family=None,
        alignment="center",
        padding=None,
        margin=None,
        target_center_y=None,
    ):
        self.fixed_font_size = font_size
        self.fixed_mask = mask
        self.font_family = font_family
        self.vertical_center_y = target_center_y
        return SimpleNamespace(
            font=SimpleNamespace(pixelSize=lambda: font_size, family=lambda: "Resolved Font"),
            line_layouts=[],
            is_overflow=False,
            reached_min_font=False,
        )

    def content_rect(self, rect, padding=None, margin=None):
        return rect

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
        self.assertAlmostEqual(renderer.vertical_center_y, 38.8)
        self.assertIsNone(renderer.vertical_bounds)

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

    def test_auto_readability_floor_scales_with_page_resolution(self):
        renderer = FakeRenderer()
        service = RenderService(
            renderer=renderer,
            config=SimpleNamespace(min_font_size=6.0, max_font_size=48.0),
        )
        bubble = TextBubble(
            id=1,
            box=Rect(0, 0, 300, 160),
            text="hello",
            text_class="text_free",
        )

        service.get_layout_for_bubble(
            "translated",
            bubble,
            image=np.zeros((3000, 2000, 3), dtype=np.uint8),
            font_family="Test",
        )

        self.assertEqual(renderer.min_size, 18.0)

    def test_source_center_is_blended_with_mask_center_by_confidence(self):
        renderer = FakeRenderer()
        service = RenderService(renderer=renderer)
        bubble = TextBubble(
            id=1,
            box=Rect(0, 0, 100, 80),
            text_box=Rect(20, 10, 40, 20),
            text="source",
            text_class="text_bubble",
            layout_confidence=0.5,
        )

        service.get_layout_for_bubble("target", bubble, image=None, font_family="Test")

        # The fallback ellipse has center 39.5; the source box center is 20.
        self.assertAlmostEqual(renderer.vertical_center_y, 35.6)

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

    def test_ellipse_fallback_sets_and_text_free_clears_mask_warning(
        self,
    ):
        service = RenderService(renderer=FakeRenderer())
        bubble = TextBubble(
            id=1,
            box=Rect(10, 10, 100, 80),
            text_box=Rect(30, 30, 40, 20),
            text_class="text_bubble",
        )

        body = service._build_bubble_body_mask(bubble, None)
        self.assertEqual(body.source, "ellipse")
        self.assertIn(
            "MASK_UNCERTAIN", bubble._derived_problem_codes
        )

        bubble.text_class = "text_free"
        self.assertIsNone(
            service._build_bubble_body_mask(bubble, None)
        )
        self.assertNotIn(
            "MASK_UNCERTAIN", bubble._derived_problem_codes
        )

    def test_expanded_component_keeps_separate_layout_bounds(self):
        service = RenderService()
        bubble = TextBubble(
            id=2,
            box=Rect(30, 30, 100, 80),
            text_box=Rect(55, 50, 40, 25),
            text_class="text_bubble",
        )
        image = np.full((180, 220, 3), 255, np.uint8)

        def fake_mask(mask_shape, *_args, **_kwargs):
            height, width = mask_shape
            mask = np.zeros((height, width), np.uint8)
            mask[
                height // 8 : height * 7 // 8,
                width // 8 : width * 7 // 8,
            ] = 255
            return BubbleClipMaskResult(
                mask,
                "detector_component",
                0.02,
            )

        with patch(
            "backend.engines.rendering.service.build_bubble_clip_mask",
            side_effect=fake_mask,
        ):
            body = service._build_bubble_body_mask(
                bubble, image
            )

        self.assertEqual(body.source, "expanded_component")
        self.assertLess(body.bounds[0], bubble.box.x)
        self.assertGreater(body.bounds[2], bubble.box.right)
        self.assertEqual(
            bubble.box, Rect(30, 30, 100, 80)
        )
        self.assertNotIn(
            "MASK_UNCERTAIN", bubble._derived_problem_codes
        )

    def test_leaking_expanded_component_falls_back_to_detector_bounds(
        self,
    ):
        service = RenderService()
        bubble = TextBubble(
            id=3,
            box=Rect(40, 40, 160, 60),
            text_box=Rect(90, 55, 50, 20),
            text_class="text_bubble",
        )
        image = np.full((180, 260, 3), 255, np.uint8)
        calls = 0

        def fake_mask(mask_shape, *_args, **_kwargs):
            nonlocal calls
            calls += 1
            height, width = mask_shape
            mask = np.zeros((height, width), np.uint8)
            mask[
                height // 8 : height * 7 // 8,
                width // 8 : width * 7 // 8,
            ] = 255
            return BubbleClipMaskResult(
                mask,
                "detector_component",
                0.25 if calls == 1 else 0.02,
            )

        with patch(
            "backend.engines.rendering.service.build_bubble_clip_mask",
            side_effect=fake_mask,
        ):
            body = service._build_bubble_body_mask(
                bubble, image
            )

        self.assertEqual(body.source, "detector_component")
        self.assertEqual(body.bounds, (40, 40, 200, 100))

if __name__ == "__main__":
    unittest.main()
