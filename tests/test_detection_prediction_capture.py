from __future__ import annotations

from types import SimpleNamespace

from scripts.capture_detection_predictions import predictions_from_blocks


def test_predictions_from_blocks_preserves_boxes_and_raw_confidence():
    blocks = [
        SimpleNamespace(xyxy=[1.2, 2.4, 10.6, 12.8], confidence=0.91),
        SimpleNamespace(xyxy=[20, 21, 30, 31], confidence=None),
    ]

    boxes, confidences = predictions_from_blocks(blocks)

    assert boxes == [[1, 2, 11, 13], [20, 21, 30, 31]]
    assert confidences == [0.91, None]
