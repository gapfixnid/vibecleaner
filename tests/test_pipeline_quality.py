from types import SimpleNamespace

from backend.pipeline.quality import AdaptiveQualityRouter


def test_detection_quality_upgrades_low_confidence_result():
    router = AdaptiveQualityRouter()
    score = router.evaluate_detection([
        SimpleNamespace(confidence=0.5), SimpleNamespace(confidence=0.6)
    ])
    assert score.passed is False
    assert score.recommended_action == "upgrade_model"
    assert router.detection_model_for("Small (INT8)", score) == "High Precision (FP32)"


def test_ocr_quality_accepts_non_empty_blocks():
    router = AdaptiveQualityRouter()
    score = router.evaluate_ocr([SimpleNamespace(text="hello"), SimpleNamespace(text="world")])
    assert score.passed is True
    assert score.score == 1.0


def test_empty_ocr_result_is_valid_empty_page_signal():
    score = AdaptiveQualityRouter().evaluate_ocr([])
    assert score.passed is True
    assert score.recommended_action == "accept"
