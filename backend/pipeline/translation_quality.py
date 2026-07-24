from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class TranslationQuality:
    passed: bool
    reason_code: str | None = None
    detail: str | None = None


_META_RESPONSE = re.compile(
    r"\b(as an ai|as a language model|here(?:'s| is) the translation|translation:)\b",
    re.IGNORECASE,
)


def _normalized(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def validate_translation(
    source: object,
    translated: object,
    *,
    source_language: str = "",
    target_language: str = "",
) -> TranslationQuality:
    source_text = _normalized(source)
    translated_text = _normalized(translated)
    if not translated_text:
        return TranslationQuality(False, "EMPTY_TRANSLATION", "Translation is empty.")
    if _META_RESPONSE.search(translated_text):
        return TranslationQuality(False, "TRANSLATION_META_RESPONSE", "Provider returned a meta response.")
    if (
        len(source_text) >= 3
        and source_text.casefold() == translated_text.casefold()
        and source_language.casefold() != target_language.casefold()
    ):
        return TranslationQuality(False, "TRANSLATION_COPIED_SOURCE", "Translation is identical to the source text.")
    if len(source_text) >= 4 and len(translated_text) > max(160, len(source_text) * 8):
        return TranslationQuality(False, "TRANSLATION_EXCESSIVE_EXPANSION", "Translation is unexpectedly long.")
    return TranslationQuality(True)
