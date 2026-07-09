from __future__ import annotations

from ...core.ports.ocr import OcrEngine
from ..context import PipelineContext
from ..strategies.engine_selection import EngineSelectionStrategy
from ..validation.results import PipelineValidationError, ValidationIssue


class OcrStage:
    name = "ocr"

    def __init__(self, ocr: OcrEngine, strategy: EngineSelectionStrategy) -> None:
        self.ocr = ocr
        self.strategy = strategy

    def run(self, context: PipelineContext) -> PipelineContext:
        detection_result = context.artifacts.get("detection_result")
        if detection_result is None:
            raise PipelineValidationError(
                [ValidationIssue(code="missing_detection", severity="error", message="detection result missing", stage=self.name)]
            )
        options = self.strategy.ocr_options(context.settings)
        context.artifacts["ocr_result"] = self.ocr.recognize(context.image, detection_result.regions, options)
        return context