import pytest

from backend.core.languages import validate_translation_language_pair


def test_supported_language_pair_is_canonicalized():
    assert validate_translation_language_pair("ja", "한국어") == ("Japanese", "Korean")


def test_same_language_pair_is_rejected():
    with pytest.raises(ValueError, match="같을 수 없습니다"):
        validate_translation_language_pair("English", "en")


def test_languages_outside_product_scope_are_rejected():
    with pytest.raises(ValueError, match="일본어, 영어, 한국어"):
        validate_translation_language_pair("Chinese", "English")
