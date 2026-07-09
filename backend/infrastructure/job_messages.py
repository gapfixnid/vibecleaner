"""Localized progress messages for background jobs.

Each key maps to a dict of ``{language_code: translated_string}``.
Fallback is always ``"en"``.
"""

from __future__ import annotations

from typing import Any

# -- message catalogue --------------------------------------------------------

_MESSAGES: dict[str, dict[str, str]] = {
    # Page translation pipeline stages
    "page_translation.detecting": {
        "en": "Detecting and reading text",
        "ko": "텍스트 감지 및 읽는 중",
    },
    "page_translation.analyzing": {
        "en": "Analyzing page layout",
        "ko": "페이지 레이아웃 분석 중",
    },
    "page_translation.translating": {
        "en": "Translating text",
        "ko": "텍스트 번역 중",
    },
    "page_translation.cleaning": {
        "en": "Cleaning backgrounds",
        "ko": "배경 정리 중",
    },
    # Batch translation
    "batch_translation.translating_page": {
        "en": "Translating page {current}/{total}...",
        "ko": "{total}페이지 중 {current}페이지 번역 중...",
    },
    "batch_translation.complete": {
        "en": "Batch translation complete",
        "ko": "일괄 번역 완료",
    },
    # Bubble translation
    "bubble.translate": {
        "en": "Translating selected bubble",
        "ko": "선택한 말풍선 번역 중",
    },
    # Inpainting
    "inpaint.bubble": {
        "en": "Cleaning single bubble",
        "ko": "단일 말풍선 정리 중",
    },
    "inpaint.page": {
        "en": "Cleaning text backgrounds",
        "ko": "텍스트 배경 정리 중",
    },
    # Model downloads
    "download.checking": {
        "en": "Checking model requirements",
        "ko": "모델 요구사항 확인 중",
    },
    "download.downloading": {
        "en": "Downloading {name}...",
        "ko": "{name} 다운로드 중...",
    },
    "download.verifying": {
        "en": "Checking downloaded models",
        "ko": "다운로드한 모델 확인 중",
    },
}


def msg(key: str, ui_language: str = "en", **params: str | int) -> str:
    """Return a localized job progress message.

    Args:
        key: Message key (e.g. ``"page_translation.detecting"``).
        ui_language: UI language code (``"ko"``, ``"en"``, …).
        **params: Optional ``{name}`` placeholders to fill.
    """
    entry = _MESSAGES.get(key)
    if entry is None:
        return key  # graceful fallback for unknown keys

    text = entry.get(ui_language) or entry.get("en") or key
    if params:
        for name, value in params.items():
            text = text.replace(f"{{{name}}}", str(value))
    return text


def msg_from_context(key: str, context: Any, **params: str | int) -> str:
    """Convenience wrapper that reads ``ui_language`` from pipeline context artifacts."""
    config = context.artifacts.get("config")
    ui_language = config.ui_language if config else "en"
    return msg(key, ui_language, **params)
