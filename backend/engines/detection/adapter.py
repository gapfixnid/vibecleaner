from __future__ import annotations

import inspect
from typing import Any

from ...core.models.geometry import Box
from ...core.models.image import ImageData
from ...core.models.text import TextRegion
from ...core.ports.detection import DetectionOptions, DetectionResult


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
        detection_kwargs = {
            "model_name": options.model_name,
            "confidence_threshold": options.confidence_threshold,
            "tiling_enabled": options.tiling_enabled,
            "bubbles_only": options.bubbles_only,
            "line_merge_sensitivity": options.line_merge_sensitivity,
            "smart_direction": options.smart_direction,
            "text_direction_override": options.text_direction_override,
        }
        if hasattr(self.engine, "detect"):
            legacy_blocks = self._call_with_supported_kwargs(self.engine.detect, image.array, detection_kwargs)
        elif hasattr(self.engine, "detect_bubbles"):
            legacy_blocks = self._call_with_supported_kwargs(self.engine.detect_bubbles, image.array, detection_kwargs)
        elif hasattr(self.engine, "detector") and hasattr(self.engine.detector, "detect_bubbles"):
            legacy_blocks = self._call_with_supported_kwargs(
                self.engine.detector.detect_bubbles,
                image.array,
                detection_kwargs,
            )
        else:
            raise TypeError("Detection engine must provide detect or detect_bubbles")
        regions = [self._to_region(block) for block in legacy_blocks]
        return DetectionResult(regions=regions, engine=self.engine_name)

    def _call_with_supported_kwargs(self, method: Any, image_array: Any, kwargs: dict[str, Any]) -> Any:
        signature = inspect.signature(method)
        if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()):
            return method(image_array, **kwargs)
        supported = {key: value for key, value in kwargs.items() if key in signature.parameters}
        return method(image_array, **supported)

    def _to_region(self, block: Any) -> TextRegion:
        coords = getattr(block, "xyxy", None) or getattr(block, "text_bbox", None)
        if coords is None:
            coords = [0, 0, 0, 0]
        x1, y1, x2, y2 = [int(value) for value in coords]
        return TextRegion(box=Box(x1=x1, y1=y1, x2=x2, y2=y2), text=str(getattr(block, "text", "") or ""))