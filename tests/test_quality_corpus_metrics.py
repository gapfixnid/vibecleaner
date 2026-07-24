from backend.pipeline.quality_evaluation import (
    character_error_rate,
    evaluate_quality_corpus,
    inpainting_outside_change_ratio,
    word_error_rate,
)
import numpy as np


def test_text_metrics_and_quality_corpus_are_deterministic():
    assert character_error_rate("안녕 세계", "안녕 세게") == 0.25
    assert word_error_rate("one two", "one three") == 0.5
    result = evaluate_quality_corpus({"cases": [{
        "case_id": "text", "expected_text": "one two", "predicted_text": "one three",
    }, {
        "case_id": "layout", "layout_overflow": True,
        "inpainting_outside_change_ratio": 0.125,
    }]})
    assert result["ocr"]["wer"] == 0.5
    assert result["layout"]["overflow_rate"] == 1.0
    assert result["inpainting"]["outside_change_ratio"] == 0.125


def test_inpainting_metric_ignores_changes_inside_mask():
    before = np.zeros((2, 3, 3), dtype=np.uint8)
    after = before.copy()
    after[0, 0] = 255
    after[1, 2] = 255
    mask = np.zeros((2, 3), dtype=np.uint8)
    mask[0, 0] = 1
    assert inpainting_outside_change_ratio(before, after, mask) == 0.2
