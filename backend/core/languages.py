"""Supported source and target languages for the translation workflow."""

SUPPORTED_TRANSLATION_LANGUAGES = ("Japanese", "English", "Korean")

_ALIASES = {
    "japanese": "Japanese", "日本語": "Japanese", "ja": "Japanese",
    "english": "English", "영어": "English", "en": "English",
    "korean": "Korean", "한국어": "Korean", "ko": "Korean",
}


def normalize_translation_language(value: str) -> str | None:
    if not isinstance(value, str):
        return None
    return _ALIASES.get(value.strip().lower())


def validate_translation_language_pair(source: str, target: str) -> tuple[str, str]:
    normalized_source = normalize_translation_language(source)
    normalized_target = normalize_translation_language(target)
    if normalized_source is None or normalized_target is None:
        raise ValueError("지원 언어는 일본어, 영어, 한국어만 사용할 수 있습니다.")
    if normalized_source == normalized_target:
        raise ValueError("원본 언어와 번역 언어는 같을 수 없습니다.")
    return normalized_source, normalized_target
