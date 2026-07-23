from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from typing import Any


@dataclass(frozen=True)
class TranslationRequestContext:
    provider: str
    model: str
    vision_enabled: bool
    image_digest: str | None
    temperature: float | None
    top_p: float | None
    max_tokens: int | None
    endpoint_identity: str | None = None


@dataclass(frozen=True)
class TranslationValue:
    index: int
    text: str


@dataclass(frozen=True)
class TranslationOutcome:
    values: tuple[TranslationValue, ...]
    effective_context: TranslationRequestContext


class VisionUnsupportedError(RuntimeError):
    def __init__(self, effective_model: str) -> None:
        super().__init__("TRANSLATION_VISION_UNSUPPORTED")
        self.effective_model = effective_model


def translate_with_legacy_adapter(
    translator: Any,
    blocks: list[Any],
    source_language: str,
    target_language: str,
    image: Any,
    requested_context: TranslationRequestContext,
) -> TranslationOutcome:
    """One-release adapter for providers that still mutate TextBlock."""
    provider_blocks = [
        block.deep_copy()
        if callable(getattr(block, "deep_copy", None))
        else deepcopy(block)
        for block in blocks
    ]
    translator.translate_blocks(
        provider_blocks,
        source_language,
        target_language,
        image,
    )
    raw_context = getattr(translator, "last_effective_context", None)
    context = requested_context
    if isinstance(raw_context, dict):
        context = TranslationRequestContext(
            provider=requested_context.provider,
            model=str(
                raw_context.get("model", requested_context.model)
            ),
            vision_enabled=bool(
                raw_context.get(
                    "vision_enabled",
                    requested_context.vision_enabled,
                )
            ),
            image_digest=(
                requested_context.image_digest
                if raw_context.get(
                    "vision_enabled",
                    requested_context.vision_enabled,
                )
                else None
            ),
            temperature=requested_context.temperature,
            top_p=requested_context.top_p,
            max_tokens=requested_context.max_tokens,
            endpoint_identity=requested_context.endpoint_identity,
        )
    return TranslationOutcome(
        values=tuple(
            TranslationValue(
                index=index,
                text=str(
                    getattr(block, "translation", "") or ""
                ),
            )
            for index, block in enumerate(provider_blocks)
        ),
        effective_context=context,
    )
