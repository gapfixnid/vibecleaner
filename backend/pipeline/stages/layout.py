from __future__ import annotations

from ...core.models.page import Bubble
from ..context import PipelineContext
from ..validation.results import PipelineValidationError, ValidationIssue


class LayoutStage:
    name = "layout"

    def run(self, context: PipelineContext) -> PipelineContext:
        ocr_result = context.artifacts.get("ocr_result")
        translation_result = context.artifacts.get("translation_result")
        translation_inputs = context.artifacts.get("translation_inputs", [])
        if ocr_result is None or translation_result is None:
            raise PipelineValidationError(
                [ValidationIssue(code="missing_text", severity="error", message="text artifacts missing", stage=self.name)]
            )

        input_ids = [item.id for item in translation_inputs]
        bubbles = []
        for index, region in enumerate(ocr_result.regions):
            input_id = input_ids[index] if index < len(input_ids) else f"region-{index}"
            bubbles.append(
                Bubble(
                    id=input_id,
                    box=region.box,
                    text=region.text,
                    translated=translation_result.translations.get(input_id, ""),
                )
            )
        context.page.bubbles = bubbles
        context.artifacts["layout_result"] = bubbles
        return context