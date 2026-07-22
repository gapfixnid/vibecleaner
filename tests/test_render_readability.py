import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QApplication

from backend.engines.rendering.renderer import TextRenderer


def _renderer() -> TextRenderer:
    app = QApplication.instance() or QApplication([])
    assert app is not None
    return TextRenderer(min_font_size=6, max_font_size=48)


def test_automatic_mask_layout_does_not_shrink_below_readability_floor():
    renderer = _renderer()
    rect = QRectF(0, 0, 90, 180)
    mask = renderer.make_ellipse_mask(90, 180, inset=3)

    layout = renderer.find_optimal_font_size_for_mask(
        "이것은 말풍선 안에 들어가기 어려울 정도로 긴 번역 문장입니다.",
        rect,
        mask,
        font_family="Arial",
    )

    assert layout.font.pixelSize() >= renderer.AUTO_READABILITY_MIN_FONT_SIZE


def test_automatic_layout_still_uses_larger_font_when_text_fits():
    renderer = _renderer()
    rect = QRectF(0, 0, 320, 180)
    mask = renderer.make_ellipse_mask(320, 180, inset=3)

    layout = renderer.find_optimal_font_size_for_mask(
        "괜찮아요.",
        rect,
        mask,
        font_family="Arial",
    )

    assert layout.font.pixelSize() > renderer.AUTO_READABILITY_MIN_FONT_SIZE
    assert layout.is_overflow is False


def test_fixed_layout_preserves_requested_size_when_text_overflows():
    renderer = _renderer()
    layout = renderer.layout_text_at_fixed_size(
        "이 문장은 아주 작은 상자 안에 들어가기에는 너무 긴 고정 크기 번역입니다.",
        QRectF(0, 0, 44, 24),
        24,
        font_family="Arial",
    )

    assert layout.font.pixelSize() == 24
    assert layout.is_overflow is True
    assert layout.reached_min_font is False
