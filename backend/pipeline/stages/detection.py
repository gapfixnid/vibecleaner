from __future__ import annotations

from ...core.ports.detection import TextDetector
from ..context import PipelineContext
from ..strategies.engine_selection import EngineSelectionStrategy
from ..validation.inputs import require_page_image


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