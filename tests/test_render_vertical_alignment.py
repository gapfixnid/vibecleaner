import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont

from backend.engines.rendering.renderer import TextLayoutResult, TextLineLayout, TextRenderer


@pytest.mark.parametrize(
    ("initial_top", "target_center"),
    [
        (10.0, 80.0),
        (80.0, 30.0),
    ],
)
def test_vertical_centering_moves_only_line_y_positions(initial_top, target_center):
    renderer = TextRenderer()
    font = QFont("Arial")
    layout = TextLayoutResult(
        font=font,
        lines=["첫째", "둘째"],
        render_width=70.0,
        line_layouts=[
            TextLineLayout("첫째", 12.0, initial_top, 70.0, 20.0),
            TextLineLayout("둘째", 12.0, initial_top + 20.0, 70.0, 20.0),
        ],
        score=1.25,
    )

    centered = renderer.center_layout_vertically(
        layout,
        target_center_y=target_center,
        bounds=QRectF(0, 0, 100, 120),
    )

    first, last = centered.line_layouts
    actual_center = (first.y + last.y + last.height) / 2.0
    assert actual_center == pytest.approx(target_center)
    assert centered.font is font
    assert centered.lines == ["첫째", "둘째"]
    assert centered.render_width == 70.0
    assert centered.score == 1.25
    assert [(line.x, line.width, line.height) for line in centered.line_layouts] == [
        (12.0, 70.0, 20.0),
        (12.0, 70.0, 20.0),
    ]


def test_vertical_centering_clamps_lines_to_bubble_bounds():
    renderer = TextRenderer()
    layout = TextLayoutResult(
        font=QFont("Arial"),
        lines=["대사"],
        render_width=60.0,
        line_layouts=[TextLineLayout("대사", 10.0, 40.0, 60.0, 20.0)],
    )

    centered = renderer.center_layout_vertically(
        layout,
        target_center_y=200.0,
        bounds=QRectF(0, 0, 100, 100),
    )

    assert centered.line_layouts[0].y == 80.0
