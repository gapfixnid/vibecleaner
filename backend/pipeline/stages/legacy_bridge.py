from __future__ import annotations

from typing import Any, Callable

from ...core.models.geometry import Box
from ...core.models.text import TextRegion
from ...core.ports.detection import DetectionOptions, DetectionResult, TextDetector
from ...core.ports.ocr import OcrEngine, OcrOptions, OcrResult
from ...core.models.image import ImageData


def _to_region(block: Any) -> TextRegion:
    coordinates = getattr(block, "xyxy", None)
    if coordinates is None:
        coordinates = getattr(block, "text_bbox", None)
    if coordinates is None:
        raise ValueError("Legacy text block has no xyxy/text_bbox coordinates")
    x1, y1, x2, y2 = [int(value) for value in coordinates]
    return TextRegion(
        box=Box(x1, y1, x2, y2),
        text=str(getattr(block, "text", "") or ""),
        confidence=getattr(block, "confidence", None),
    )


class LegacyDetectionAdapter(TextDetector):
    """Expose a legacy detector callable behind the v2 detection port."""

    def __init__(self, detect_fn: Callable[..., list[Any]]) -> None:
        self.detect_fn = detect_fn

    def detect(self, image: ImageData, options: DetectionOptions) -> DetectionResult:
        blocks = self.detect_fn(
            image.array,
            model_name=options.model_name,
            confidence_threshold=options.confidence_threshold,
            tiling_enabled=options.tiling_enabled,
            bubbles_only=options.bubbles_only,
            line_merge_sensitivity=options.line_merge_sensitivity,
            smart_direction=options.smart_direction,
            text_direction_override=options.text_direction_override,
        )
        return DetectionResult(regions=[_to_region(block) for block in blocks], engine="legacy")


class LegacyOcrAdapter(OcrEngine):
    """Expose a legacy OCR callable behind the v2 OCR port."""

    def __init__(self, recognize_fn: Callable[..., Any]) -> None:
        self.recognize_fn = recognize_fn

    def recognize(self, image: ImageData, regions: list[TextRegion], options: OcrOptions) -> OcrResult:
        blocks = [type("LegacyBlock", (), {"xyxy": region.box_to_xyxy() if hasattr(region, "box_to_xyxy") else [region.box.x1, region.box.y1, region.box.x2, region.box.y2], "text": region.text})() for region in regions]
        self.recognize_fn(image.array, blocks, engine=options.engine)
        for region, block in zip(regions, blocks):
            region.text = str(getattr(block, "text", "") or "")
        return OcrResult(regions=regions, engine="legacy")
