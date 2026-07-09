from __future__ import annotations

from typing import Any

from ...core.ports.translation import TranslationInput, TranslationOptions, TranslationResult


class TranslationEngineAdapter:
    def __init__(self, engine: Any, engine_name: str | None = None) -> None:
        self.engine = engine
        self.engine_name = engine_name or engine.__class__.__name__

    def translate_batch(
        self,
        items: list[TranslationInput],
        options: TranslationOptions,
    ) -> TranslationResult:
        translations = {
            item.id: self.engine.translate(item.text, options.source_language, options.target_language)
            for item in items
        }
        return TranslationResult(translations=translations, engine=self.engine_name)