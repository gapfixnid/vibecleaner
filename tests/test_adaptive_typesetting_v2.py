import os

import cv2
import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QFontMetricsF
from PySide6.QtWidgets import QApplication

from backend.engines.rendering.renderer import TextRenderer
from backend.engines.rendering.typesetting import unicode_break_tokens


@pytest.fixture(scope="module")
def renderer() -> TextRenderer:
    app = QApplication.instance() or QApplication([])
    assert app is not None
    return TextRenderer(min_font_size=6, max_font_size=48)


def test_unicode_tokenizer_preserves_semantic_groups_until_grapheme_fallback():
    text = "안녕하세요 123kg (테스트) https://example.com/a"

    primary = unicode_break_tokens(text)
    fallback = unicode_break_tokens(text, allow_grapheme_breaks=True)

    assert any("안녕하세요" in token for token in primary)
    assert any("123kg" in token for token in primary)
    assert any("(테스트)" in token for token in primary)
    assert any("https://example.com/a" in token for token in primary)
    assert fallback[:5] == list("안녕하세요")


def test_rectangle_wrapping_preserves_explicit_newlines(renderer: TextRenderer):
    font = QFont("Arial")
    font.setPixelSize(18)

    lines = renderer.wrap_korean_text(
        "첫 번째 줄\n둘째 줄",
        300,
        font,
        allow_char_break=False,
    )

    assert lines == ["첫 번째 줄", "둘째 줄"]


def test_distance_safe_mask_applies_padding_and_asymmetric_insets(renderer: TextRenderer):
    mask = np.zeros((120, 140), dtype=np.uint8)
    mask[10:110, 10:130] = 1

    compact = renderer.make_safe_mask(mask, padding={"top": 2, "right": 2, "bottom": 2, "left": 2})
    padded = renderer.make_safe_mask(
        mask,
        padding={"top": 8, "right": 6, "bottom": 8, "left": 20},
        stroke_width=2,
    )

    assert np.count_nonzero(padded) < np.count_nonzero(compact)
    padded_ys, padded_xs = np.where(padded)
    assert padded_xs.min() >= 32  # mask left 10 + 20px padding + 2px stroke
    assert padded_xs.max() <= 121  # mask right 129 - 6px padding - 2px stroke
    assert padded_ys.min() >= 20


def test_line_slots_use_a_single_contiguous_safe_segment(renderer: TextRenderer):
    mask = np.zeros((40, 100), dtype=np.uint8)
    mask[:, 5:35] = 1
    mask[:, 60:95] = 1

    slots = renderer._line_slots_from_mask(mask, QRectF(0, 0, 100, 40), 10, 10)

    assert slots
    assert all(slot.x >= 60 for slot in slots)
    assert all(slot.x + slot.width <= 95 for slot in slots)


def _shape_mask(kind: str) -> np.ndarray:
    if kind == "circle":
        mask = np.zeros((180, 180), dtype=np.uint8)
        cv2.ellipse(mask, (90, 90), (82, 82), 0, 0, 360, 1, -1)
        return mask
    if kind == "tall":
        mask = np.zeros((220, 120), dtype=np.uint8)
        cv2.ellipse(mask, (60, 110), (54, 102), 0, 0, 360, 1, -1)
        return mask
    if kind == "wide":
        mask = np.zeros((120, 260), dtype=np.uint8)
        cv2.ellipse(mask, (130, 60), (122, 54), 0, 0, 360, 1, -1)
        return mask
    mask = np.zeros((180, 220), dtype=np.uint8)
    polygon = np.array([[12, 45], [78, 12], [205, 30], [214, 135], [135, 170], [25, 150]])
    cv2.fillPoly(mask, [polygon], 1)
    return mask


@pytest.mark.parametrize("kind", ["circle", "tall", "wide", "asymmetric"])
def test_shape_layout_is_deterministic_and_stays_in_safe_mask(renderer: TextRenderer, kind: str):
    mask = _shape_mask(kind)
    height, width = mask.shape
    rect = QRectF(0, 0, width, height)
    text = "안녕하세요 반가워요 오늘도 좋은 하루예요"
    padding = {"top": 4, "right": 4, "bottom": 4, "left": 4}

    first = renderer.find_optimal_font_size_for_mask(
        text,
        rect,
        mask,
        font_family="Arial",
        padding=padding,
    )
    second = renderer.find_optimal_font_size_for_mask(
        text,
        rect,
        mask,
        font_family="Arial",
        padding=padding,
    )

    signature = lambda layout: (
        layout.font.pixelSize(),
        layout.line_height_ratio,
        [(line.text, line.x, line.y, line.width, line.height) for line in layout.line_layouts],
    )
    assert signature(first) == signature(second)
    assert first.font.pixelSize() >= renderer.AUTO_READABILITY_MIN_FONT_SIZE
    assert all(len(line.strip()) > 1 for line in first.lines)
    assert first.is_overflow is False

    relaxed_safe = renderer.make_safe_mask(mask, padding=padding, inset_scale=0.7)
    glyph_height = int(np.ceil(QFontMetricsF(first.font).height()))
    for line in first.line_layouts:
        x1 = max(0, int(np.floor(line.x - rect.x())))
        x2 = min(width, int(np.ceil(line.x - rect.x() + line.width)))
        y1 = max(0, int(np.floor(line.y - rect.y())))
        y2 = min(height, y1 + glyph_height)
        assert x2 > x1 and y2 > y1
        assert bool(np.all(relaxed_safe[y1:y2, x1:x2]))
