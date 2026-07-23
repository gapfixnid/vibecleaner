from __future__ import annotations

import numpy as np

from backend.engines.common.textblock import TextBlock
from backend.engines.detection.pipeline import DetectionPipeline
from backend.pipeline.analysis.bubbles import BubbleAnalysisService
from backend.pipeline.page_analysis import bubbles_from_analysis


def test_detection_pipeline_preserves_model_confidence_on_text_blocks():
    image = np.full((40, 40, 3), 255, dtype=np.uint8)
    blocks = DetectionPipeline().build_text_blocks(
        image,
        np.array([[5, 5, 25, 25]]),
        np.empty((0, 4), dtype=np.int32),
        text_confidences={(5, 5, 25, 25): 0.87},
    )

    assert len(blocks) == 1
    assert blocks[0].confidence == 0.87


def test_clamped_text_box_keeps_raw_detector_confidence():
    image = np.full((40, 40, 3), 255, dtype=np.uint8)
    blocks = DetectionPipeline().build_text_blocks(
        image,
        np.array([[-4, 5, 25, 25]]),
        np.empty((0, 4), dtype=np.int32),
        text_confidences={(-4, 5, 25, 25): 0.73},
    )

    assert blocks[0].confidence == 0.73


def test_tiny_overlap_without_center_inside_is_not_associated():
    image = np.full((100, 100, 3), 255, dtype=np.uint8)
    blocks = DetectionPipeline().build_text_blocks(
        image,
        np.array([[40, 40, 70, 70]]),
        np.array([[68, 68, 98, 98]]),
    )

    assert blocks[0].bubble_match_id is None
    assert blocks[0].text_class == "text_free"


def test_duplicate_bubble_boxes_do_not_create_false_ambiguity():
    image = np.full((100, 100, 3), 255, dtype=np.uint8)
    duplicate = [10, 10, 80, 80]
    blocks = DetectionPipeline().build_text_blocks(
        image,
        np.array([[30, 30, 60, 60]]),
        np.array([duplicate, duplicate]),
    )

    assert blocks[0].bubble_match_id == 0
    assert not blocks[0].ambiguous_match


def test_bubble_analysis_keeps_raw_model_confidence_separate_from_heuristic_score():
    block = TextBlock(
        text_bbox=np.array([5, 5, 25, 25]),
        text="text",
        confidence=0.41,
    )
    analysis = BubbleAnalysisService().analyze(
        np.full((40, 40, 3), 255, dtype=np.uint8),
        [block],
        source_lang="Japanese",
    )

    assert analysis.bubbles[0].model_confidence == 0.41
    assert analysis.bubbles[0].confidence != analysis.bubbles[0].model_confidence


def test_page_analysis_exports_model_confidence_when_available():
    block = TextBlock(
        text_bbox=np.array([5, 5, 25, 25]),
        text="text",
        confidence=0.41,
    )
    image = np.full((40, 40, 3), 255, dtype=np.uint8)
    result = bubbles_from_analysis(
        image,
        [block],
        "Japanese",
        "Korean",
        config=type("Config", (), {"bubbles_only": False})(),
        page_analysis_service=type("Page", (), {"analyze": lambda self, *args, **kwargs: type(
            "PageResult", (), {"reading_order": type("Order", (), {"direction": "ltr"})(), "writing_mode": "horizontal"}
        )()})(),
        bubble_analysis_service=BubbleAnalysisService(),
        layout_planner_service=type("Layout", (), {"plan": lambda self, *args, **kwargs: type(
            "Plan", (), {
                "alignment": "center", "writing_mode": "horizontal", "text_direction": "ltr",
                "justification": "none", "padding": None, "margin": None, "confidence": 0.8,
                "reasoning": "test",
            }
        )()})(),
    )

    assert result[0].detection_confidence == 0.41
