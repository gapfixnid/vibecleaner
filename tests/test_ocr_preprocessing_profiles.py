from backend.engines.ocr.preprocessing_profile import resolve_ocr_preprocessing_profile


def test_profiles_choose_language_and_engine_defaults():
    profile = resolve_ocr_preprocessing_profile("Japanese", "manga_ocr")
    assert profile.padding == 8
    assert profile.adaptive_binarization is False
    assert resolve_ocr_preprocessing_profile("English", "ppocr") == (
        resolve_ocr_preprocessing_profile("영어", "fast")
    )
    assert resolve_ocr_preprocessing_profile("English", "ppocr").crop_scale == 1.25
    assert resolve_ocr_preprocessing_profile("Korean", "ppocr").crop_scale == 1.4


def test_profile_explicit_values_override_defaults():
    profile = resolve_ocr_preprocessing_profile(
        "English", "ppocr", padding=13, crop_scale=2.25,
        adaptive_binarization=False, adaptive_binarization_strength=3.5,
    )
    assert profile.padding == 13
    assert profile.crop_scale == 2.25
    assert profile.adaptive_binarization is False
    assert profile.adaptive_binarization_strength == 3.5
