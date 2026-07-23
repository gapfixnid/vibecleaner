from __future__ import annotations

from dataclasses import dataclass

from ...core.text.graphemes import (
    grapheme_count,
    has_repeated_grapheme,
    script_ratio,
)


@dataclass(frozen=True)
class OcrSnapshot:
    text: str
    confidence: float | None


@dataclass(frozen=True)
class OcrRetryDecision:
    accepted: bool
    selected: OcrSnapshot
    reason: str
    uncertain: bool


def _language_mismatch(text: str, language: str) -> bool:
    count = grapheme_count(text)
    if count < 6:
        return False
    normalized = str(language or "").strip().lower()
    if normalized not in {"japanese", "日本語", "ja"}:
        return False
    ratio = script_ratio(text, "japanese")
    if count < 12:
        return ratio < 0.10
    return ratio < 0.25


def choose_ocr_retry(
    original: OcrSnapshot,
    candidate: OcrSnapshot,
    language: str,
) -> OcrRetryDecision:
    original_length = grapheme_count(original.text)
    candidate_length = grapheme_count(candidate.text)
    invalid = (
        candidate_length == 0
        or candidate_length > 128
        or has_repeated_grapheme(candidate.text, threshold=9)
        or _language_mismatch(candidate.text, language)
    )
    if invalid:
        return OcrRetryDecision(
            False, original, "invalid_candidate", True
        )

    suspicious_original = original_length <= 2
    if suspicious_original:
        if original_length > 0 and candidate_length > max(
            12, original_length * 4
        ):
            return OcrRetryDecision(
                False, original, "suspicious_length_expansion", True
            )
        if candidate.confidence is None:
            return OcrRetryDecision(
                False, original, "candidate_confidence_missing", True
            )
        if original.confidence is None:
            accepted = candidate.confidence >= 0.55
        else:
            accepted = candidate.confidence >= max(
                0.40, original.confidence - 0.05
            )
        return OcrRetryDecision(
            accepted,
            candidate if accepted else original,
            "suspicious_recovery"
            if accepted
            else "suspicious_low_confidence",
            not accepted,
        )

    if candidate.confidence is None:
        return OcrRetryDecision(
            False, original, "candidate_confidence_missing", True
        )
    if original.confidence is None:
        return OcrRetryDecision(
            False, original, "original_confidence_missing", True
        )
    accepted = candidate.confidence >= original.confidence + 0.05
    return OcrRetryDecision(
        accepted,
        candidate if accepted else original,
        "confidence_improved" if accepted else "not_improved",
        not accepted,
    )
