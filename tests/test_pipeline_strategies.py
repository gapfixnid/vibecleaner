from core.config import AppConfigSnapshot
from pipeline.strategies.engine_selection import EngineSelectionStrategy


def test_detection_options_are_resolved_from_snapshot():
    settings = AppConfigSnapshot(
        detect_model="Small (INT8)",
        confidence_threshold=0.42,
        tiling_enabled=False,
        ocr_engine="balanced",
        inpaint_engine="opencv",
    )

    options = EngineSelectionStrategy().detection_options(settings)

    assert options.model_name == "Small (INT8)"
    assert options.confidence_threshold == 0.42
    assert options.tiling_enabled is False


def test_ocr_and_inpainting_options_are_resolved_from_snapshot():
    settings = AppConfigSnapshot(ocr_engine="manga", ocr_padding=12, ocr_crop_scale=2.0, inpaint_engine="opencv")
    strategy = EngineSelectionStrategy()

    ocr_options = strategy.ocr_options(settings)
    inpaint_options = strategy.inpaint_options(settings)

    assert ocr_options.engine == "manga"
    assert ocr_options.padding == 12
    assert ocr_options.crop_scale == 2.0
    assert inpaint_options.engine == "opencv"


def test_render_options_are_resolved_from_snapshot():
    settings = AppConfigSnapshot(min_font_size=7.0, max_font_size=44.0, default_font_size=19.0)

    options = EngineSelectionStrategy().render_options(settings)

    assert options.min_font_size == 7.0
    assert options.max_font_size == 44.0
    assert options.default_font_size == 19.0
