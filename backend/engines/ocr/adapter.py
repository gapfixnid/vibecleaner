from __future__ import annotations

from dataclasses import replace
from typing import Any

from ...core.models.image import ImageData
from ...core.models.text import TextRegion
from ...core.ports.ocr import OcrOptions, OcrResult
from ..common.textblock import TextBlock


class OcrEngineAdapter:
    def __init__(self, engine: Any, engine_name: str | None = None) -> None:
        self.engine = engine
        self.engine_name = engine_name or engine.__class__.__name__

    def recognize(self, image: ImageData, regions: list[TextRegion], options: OcrOptions) -> OcrResult:
        if hasattr(self.engine, "recognize"):
            texts = self.engine.recognize(image.array, regions, options)
        else:
            blocks = [
                TextBlock(text_bbox=[region.box.x1, region.box.y1, region.box.x2, region.box.y2], text=region.text)
                for region in regions
            ]
            recognized_blocks = self.engine.recognize_text(
                image.array,
                blocks,
                engine=options.engine,
                padding=options.padding,
                crop_scale=options.crop_scale,
                adaptive_binarization=options.adaptive_binarization,
                adaptive_binarization_strength=options.adaptive_binarization_strength,
            )
            # Keep the recognized block coordinates so results can be matched
            # back to the original regions even if the OCR engine reorders them.
            texts = recognized_blocks
        recognized = [
            replace(
                region,
                text=self._text_for_region(region, texts, index),
                ocr_confidence=self._confidence_for_region(region, texts, index),
            )
            for index, region in enumerate(regions)
        ]
        return OcrResult(regions=recognized, engine=self.engine_name)

    @staticmethod
    def _region_key(region: Any) -> tuple[int, int, int, int] | None:
        box = getattr(region, "box", None)
        if box is not None and all(hasattr(box, name) for name in ("x1", "y1", "x2", "y2")):
            return tuple(int(getattr(box, name)) for name in ("x1", "y1", "x2", "y2"))
        coordinates = getattr(region, "xyxy", None)
        if coordinates is not None and len(coordinates) >= 4:
            return tuple(int(value) for value in coordinates[:4])
        return None

    @classmethod
    def _text_for_region(cls, region: TextRegion, results: Any, index: int) -> str:
        if not isinstance(results, (list, tuple)):
            return region.text

        target_key = cls._region_key(region)
        if target_key is not None:
            for result in results:
                if cls._region_key(result) == target_key:
                    return str(getattr(result, "text", result) or "")

        if index < len(results):
            result = results[index]
            return str(getattr(result, "text", result) or "")
        return region.text

    @classmethod
    def _confidence_for_region(cls, region: TextRegion, results: Any, index: int) -> float | None:
        if not isinstance(results, (list, tuple)):
            return None
        target_key = cls._region_key(region)
        candidates = results
        if target_key is not None:
            candidates = [result for result in results if cls._region_key(result) == target_key]
        if not candidates and index < len(results):
            candidates = [results[index]]
        if not candidates:
            return None
        value = getattr(candidates[0], "ocr_confidence", None)
        return float(value) if value is not None else None
