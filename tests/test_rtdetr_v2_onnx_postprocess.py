from backend.engines.detection.rtdetr_v2_onnx import RTDetrV2ONNXDetection


def test_select_detection_boxes_applies_score_threshold_and_class_mapping():
    candidates = [
        (0, [1, 2, 30, 40], 0.91),
        (1, [4, 5, 20, 25], 0.80),
        (2, [8, 9, 24, 29], 0.20),
    ]

    bubbles, texts = RTDetrV2ONNXDetection._select_detection_boxes(
        candidates,
        threshold=0.3,
    )

    assert bubbles == [[1, 2, 30, 40]]
    assert texts == [[4, 5, 20, 25]]


def test_low_confidence_recall_pass_recovers_text_when_primary_pass_is_empty():
    candidates = [
        (0, [1, 2, 30, 40], 0.91),
        (1, [4, 5, 20, 25], 0.31),
    ]
    primary_bubbles, primary_text = RTDetrV2ONNXDetection._select_detection_boxes(
        candidates,
        threshold=0.45,
    )
    assert primary_bubbles == [[1, 2, 30, 40]]
    assert primary_text == []

    recall_bubbles, recall_text = RTDetrV2ONNXDetection._select_detection_boxes(
        candidates,
        threshold=max(0.15, 0.45 * 0.65),
    )
    assert recall_bubbles == [[1, 2, 30, 40]]
    assert recall_text == [[4, 5, 20, 25]]


def test_recall_threshold_does_not_override_existing_high_confidence_text():
    candidates = [
        (1, [4, 5, 20, 25], 0.80),
        (2, [8, 9, 24, 29], 0.20),
    ]
    _, primary_text = RTDetrV2ONNXDetection._select_detection_boxes(
        candidates,
        threshold=0.45,
    )
    assert primary_text == [[4, 5, 20, 25]]
