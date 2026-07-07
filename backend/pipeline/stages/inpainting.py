from __future__ import annotations

from core.ports.inpainting import InpaintRegion, Inpainter
from pipeline.context import PipelineContext
from pipeline.strategies.engine_selection import EngineSelectionStrategy
from pipeline.validation.results import PipelineValidationError, ValidationIssue


class InpaintingStage:
    name = "inpainting"

    def __init__(self, inpainter: Inpainter, strategy: EngineSelectionStrategy) -> None:
        self.inpainter = inpainter
        self.strategy = strategy

    def run(self, context: PipelineContext) -> PipelineContext:
        detection_result = context.artifacts.get("detection_result")
        if detection_result is None:
            raise PipelineValidationError(
                [ValidationIssue(code="missing_detection", severity="error", message="detection result missing", stage=self.name)]
            )
        regions = [InpaintRegion(box=region.box) for region in detection_result.regions]
        options = self.strategy.inpaint_options(context.settings)
        context.artifacts["inpaint_regions"] = regions
        context.artifacts["inpaint_result"] = self.inpainter.inpaint(context.image, regions, options)
        context.image = context.artifacts["inpaint_result"].image
        return context
