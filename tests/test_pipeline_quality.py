from types import SimpleNamespace

import numpy as np

from backend.pipeline.quality import AdaptiveQualityRouter


def test_detection_quality_upgrades_low_confidence_result():
    router = AdaptiveQualityRouter()
    score = router.evaluate_detection([
        SimpleNamespace(confidence=0.5), SimpleNamespace(confidence=0.6)
    ])
    assert score.passed is False
    assert score.recommended_action == "upgrade_model"
    assert router.detection_model_for("Small (INT8)", score) == "High Precision (FP32)"


def test_quality_router_selects_highest_quality_compatible_catalog_profile():
    from backend.core.providers import ProviderCapabilities, ProviderManifest, ProviderModelProfile

    manifest = ProviderManifest(
        provider_id="test.ocr",
        display_name="Test OCR",
        stage="ocr",
        api_version="1",
        implementation_version="test",
        capabilities=ProviderCapabilities(),
        resource_classes={"cpu"},
        model_catalog=(
            ProviderModelProfile("fast", "Fast", 0.70, 0.95, frozenset({"cpu"})),
            ProviderModelProfile("balanced", "Balanced", 0.90, 0.55, frozenset({"cpu"})),
        ),
    )
    score = AdaptiveQualityRouter().evaluate_ocr([SimpleNamespace(text="")])
    assert AdaptiveQualityRouter().select_model("ocr", "fast", score, manifest) == "balanced"


def test_ocr_quality_accepts_non_empty_blocks():
    router = AdaptiveQualityRouter()
    score = router.evaluate_ocr([SimpleNamespace(text="hello"), SimpleNamespace(text="world")])
    assert score.passed is True
    assert score.score == 1.0


def test_ocr_quality_uses_language_threshold_and_raw_confidence():
    router = AdaptiveQualityRouter()
    blocks = [
        SimpleNamespace(text="hello", ocr_confidence=0.91),
        SimpleNamespace(text="world", ocr_confidence=0.81),
        SimpleNamespace(text="again", ocr_confidence=0.71),
        SimpleNamespace(text="", ocr_confidence=0.22),
    ]

    english = router.evaluate_ocr(blocks, "English")
    japanese = router.evaluate_ocr(blocks, "Japanese")

    assert english.passed
    assert not japanese.passed
    assert english.signals["threshold"] == 0.75
    assert english.signals["raw_confidence_available_ratio"] == 1.0
    assert english.signals["raw_confidence_mean"] == 0.6625


def test_empty_ocr_result_is_valid_empty_page_signal():
    score = AdaptiveQualityRouter().evaluate_ocr([])
    assert score.passed is True
    assert score.recommended_action == "accept"


def test_detection_without_confidence_does_not_trigger_speculative_replan():
    score = AdaptiveQualityRouter().evaluate_detection([SimpleNamespace()])
    assert score.passed is True
    assert score.signals["confidence_available"] == 0.0


def test_inpainting_quality_rejects_noop_result():
    image = np.zeros((12, 12, 3), dtype=np.uint8)
    score = AdaptiveQualityRouter().evaluate_inpainting(image, image.copy(), [[2, 2, 8, 8]])
    assert score.passed is False
    assert score.recommended_action == "retry_inpainting"


def test_inpainting_quality_accepts_target_change_on_uniform_source():
    image = np.zeros((12, 12, 3), dtype=np.uint8)
    result = image.copy()
    result[2:8, 2:8] = 255
    score = AdaptiveQualityRouter().evaluate_inpainting(image, result, [[2, 2, 8, 8]])
    assert score.passed is True
    assert score.signals["target_change_ratio"] == 1.0
