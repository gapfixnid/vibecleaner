from __future__ import annotations

from ...core.ports.translation import TranslationInput, Translator
from ..context import PipelineContext
from ..strategies.engine_selection import EngineSelectionStrategy
from ..validation.results import PipelineValidationError, ValidationIssue


class TranslationStage:
    name = "translation"

    def __init__(self, translator: Translator, strategy: EngineSelectionStrategy) -> None:
        self.translator = translator
        self.strategy = strategy

    def run(self, context: PipelineContext) -> PipelineContext:
        ocr_result = context.artifacts.get("ocr_result")
        if ocr_result is None:
            raise PipelineValidationError(
                [ValidationIssue(code="missing_ocr", severity="error", message="ocr result missing", stage=self.name)]
            )
        items = [
            TranslationInput(id=f"region-{index}", text=region.text)
            for index, region in enumerate(ocr_result.regions)
        ]
        options = self.strategy.translation_options(context.settings)
        context.artifacts["translation_inputs"] = items
        context.artifacts["translation_result"] = self.translator.translate_batch(items, options)
        return context