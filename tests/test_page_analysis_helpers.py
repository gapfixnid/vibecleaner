import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from core.models import Rect

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import pipeline.page_analysis as page_analysis
from core.models import TextBubble
from core.config import AppConfig
from pipeline.analysis.bubbles import BubbleAnalysisResult, BubbleData
from core.models import Insets


def test_bubbles_from_analysis_preserves_detected_font_color():
    config = AppConfig()
    image = np.zeros((40, 40, 3), dtype=np.uint8)
    bubble_data = BubbleData(
        bubble_box=(2, 3, 20, 21),
        text_box=(4, 5, 18, 19),
        layout_box=(5, 6, 17, 18),
        text="hello",
        text_class="text_bubble",
        font_color=(12, 34, 56),
    )

    bubbles = page_analysis.bubbles_from_analysis(
        image,
        blocks=[],
        source_lang="Japanese",
        target_lang="Korean",
        config=config,
        page_analysis_service=SimpleNamespace(
            analyze=lambda *args, **kwargs: SimpleNamespace(
                reading_order=SimpleNamespace(direction="ltr"),
                writing_mode="horizontal",
            )
        ),
        bubble_analysis_service=SimpleNamespace(
            analyze=lambda *args, **kwargs: BubbleAnalysisResult(
                bubbles=[bubble_data],
                reading_order="LTR",
                writing_mode="horizontal",
            )
        ),
        layout_planner_service=SimpleNamespace(plan=lambda *args, **kwargs: SimpleNamespace(alignment="center")),
    )

    assert len(bubbles) == 1
    assert bubbles[0].color == "#0c2238"


def test_bubbles_from_analysis_preserves_layout_plan_metadata():
    config = AppConfig()
    image = np.zeros((40, 40, 3), dtype=np.uint8)
    bubble_data = BubbleData(
        bubble_box=(2, 3, 30, 31),
        text_box=(4, 5, 28, 29),
        layout_box=(8, 9, 24, 25),
        text="hello",
        text_class="text_bubble",
    )

    bubbles = page_analysis.bubbles_from_analysis(
        image,
        blocks=[],
        source_lang="Japanese",
        target_lang="Korean",
        config=config,
        page_analysis_service=SimpleNamespace(
            analyze=lambda *args, **kwargs: SimpleNamespace(
                reading_order=SimpleNamespace(direction="rtl"),
                writing_mode="vertical",
            )
        ),
        bubble_analysis_service=SimpleNamespace(
            analyze=lambda *args, **kwargs: BubbleAnalysisResult(
                bubbles=[bubble_data],
                reading_order="RTL",
                writing_mode="vertical",
            )
        ),
        layout_planner_service=SimpleNamespace(
            plan=lambda *args, **kwargs: SimpleNamespace(
                alignment="right",
                writing_mode="vertical",
                text_direction="rtl",
                justification="full",
                padding=Insets(top=1, right=2, bottom=3, left=4),
                margin=Insets(top=5, right=6, bottom=7, left=8),
                confidence=0.73,
                reasoning="writing_mode=vertical; alignment=right",
            )
        ),
    )

    assert len(bubbles) == 1
    bubble = bubbles[0]
    assert bubble.layout_box == Rect(8, 9, 16, 16)
    assert bubble.font_family == ""
    assert bubble.alignment == "right"
    assert bubble.writing_mode == "vertical"
    assert bubble.text_direction == "rtl"
    assert bubble.justification == "full"
    assert bubble.layout_padding == {"top": 1, "right": 2, "bottom": 3, "left": 4}
    assert bubble.layout_margin == {"top": 5, "right": 6, "bottom": 7, "left": 8}
    assert bubble.layout_confidence == 0.73
    assert bubble.layout_reasoning == "writing_mode=vertical; alignment=right"


def test_merge_overlapping_bubbles_preserves_cjk_lines_without_spaces():
    first = TextBubble(
        id=1,
        box=Rect(10, 10, 30, 30),
        text_box=Rect(12, 12, 10, 10),
        text="こん",
        translated="안녕",
    )
    second = TextBubble(
        id=2,
        box=Rect(12, 12, 30, 30),
        text_box=Rect(20, 20, 10, 10),
        text="にちは",
        translated="하세요",
    )

    merged = page_analysis.merge_overlapping_bubbles([first, second])

    assert len(merged) == 1
    assert merged[0].text == "こん\nにちは"
    assert merged[0].translated == "안녕\n하세요"
