from __future__ import annotations

from typing import Any

from core.models.geometry import Box
from core.models.image import ImageData
from core.models.text import TextRegion
from core.ports.detection import DetectionOptions, DetectionResult


class DetectionEngineAdapter:
    def __init__(self, engine: Any, engine_name: str | None = None) -> None:
        self.engine = engine
        self.engine_name = engine_name or engine.__class__.__name__

    def detect(self, image: ImageData, options: DetectionOptions) -> DetectionResult:
        if hasattr(self.engine, "initialize"):
            self.engine.initialize(
                model_name=options.model_name,
                confidence_threshold=options.confidence_threshold,
                tiling_enabled=options.tiling_enabled,
            )
        if hasattr(self.engine, "detect"):
            legacy_blocks = self.engine.detect(image.array)
        elif hasattr(self.engine, "detect_bubbles"):
            legacy_blocks = self.engine.detect_bubbles(
                image.array,
                model_name=options.model_name,
                confidence_threshold=options.confidence_threshold,
                tiling_enabled=options.tiling_enabled,
            )
        elif hasattr(self.engine, "detector") and hasattr(self.engine.detector, "detect_bubbles"):
            legacy_blocks = self.engine.detector.detect_bubbles(
                image.array,
                model_name=options.model_name,
                confidence_threshold=options.confidence_threshold,
                tiling_enabled=options.tiling_enabled,
            )
        else:
            raise TypeError("Detection engine must provide detect or detect_bubbles")
        regions = [self._to_region(block) for block in legacy_blocks]
        return DetectionResult(regions=regions, engine=self.engine_name)

    def _to_region(self, block: Any) -> TextRegion:
        coords = getattr(block, "xyxy", None) or getattr(block, "text_bbox", None)
        if coords is None:
            coords = [0, 0, 0, 0]
        x1, y1, x2, y2 = [int(value) for value in coords]
        return TextRegion(box=Box(x1=x1, y1=y1, x2=x2, y2=y2), text=str(getattr(block, "text", "") or ""))
