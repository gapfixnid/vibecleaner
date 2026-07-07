from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class TranslationInput:
    id: str
    text: str


@dataclass(frozen=True)
class TranslationOptions:
    provider: str = "google"
    source_language: str = "auto"
    target_language: str = "ko"
    model: str = ""


@dataclass
class TranslationResult:
    translations: dict[str, str] = field(default_factory=dict)
    engine: str | None = None


class Translator(Protocol):
    def translate_batch(
        self,
        items: list[TranslationInput],
        options: TranslationOptions,
    ) -> TranslationResult:
        ...
