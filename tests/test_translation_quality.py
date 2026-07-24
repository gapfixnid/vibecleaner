from backend.pipeline.translation_quality import validate_translation


def test_empty_translation_is_flagged():
    result = validate_translation("hello", "", source_language="English", target_language="Korean")
    assert not result.passed
    assert result.reason_code == "EMPTY_TRANSLATION"


def test_source_copy_is_flagged_only_for_different_languages():
    result = validate_translation("hello world", "hello world", source_language="English", target_language="Korean")
    assert result.reason_code == "TRANSLATION_COPIED_SOURCE"
    assert validate_translation("hello", "hello", source_language="English", target_language="English").passed


def test_provider_meta_response_and_excessive_expansion_are_flagged():
    assert validate_translation("hello", "As an AI, I cannot translate this.").reason_code == "TRANSLATION_META_RESPONSE"
    assert validate_translation("word", "x" * 161).reason_code == "TRANSLATION_EXCESSIVE_EXPANSION"

