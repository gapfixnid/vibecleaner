from __future__ import annotations

from core.ports.detection import TextDetector
from pipeline.context import PipelineContext
from pipeline.strategies.engine_selection import EngineSelectionStrategy
from pipeline.validation.inputs import require_page_image


class DetectionStage:
    name = "detection"

    def __init__(self, detector: TextDetector, strategy: EngineSelectionStrategy) -> None:
        self.detector = detector
        self.strategy = strategy

    def run(self, context: PipelineContext) -> PipelineContext:
        require_page_image(context, self.name)
        options = self.strategy.detection_options(context.settings)
        context.artifacts["detection_result"] = self.detector.detect(context.image, options)
        return context
