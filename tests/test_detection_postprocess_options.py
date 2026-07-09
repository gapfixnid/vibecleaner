import numpy as np

from backend.core.config import AppConfigSnapshot
from backend.engines.detection.pipeline import DetectionPipeline
from backend.pipeline.strategies.engine_selection import EngineSelectionStrategy

def test_strategy_maps_detection_postprocess_options():
    settings = AppConfigSnapshot(
        bubbles_only=True,
        line_merge_sensitivity=1.7,
        smart_direction=False,
        text_direction_override="vertical",
    )

    options = EngineSelectionStrategy().detection_options(settings)

    assert options.bubbles_only is True
    assert options.line_merge_sensitivity == 1.7
    assert options.smart_direction is False
    assert options.text_direction_override == "vertical"

def test_detection_pipeline_accepts_explicit_bubbles_only_option():
    pipeline = DetectionPipeline(settings=None)
    image = np.full((24, 24, 3), 255, dtype=np.uint8)
    text_boxes = np.array([[6, 6, 14, 14]])
    bubble_boxes = np.array([[2, 2, 18, 18]])

    blocks = pipeline.build_text_blocks(
        image,
        text_boxes,
        bubble_boxes,
        bubbles_only=False,
        line_merge_sensitivity=1.7,
        smart_direction=False,
        text_direction_override="horizontal",
    )

    assert blocks[0].text_class == "text_bubble"
