from __future__ import annotations

from dataclasses import replace
from typing import Any

from core.models.image import ImageData
from core.models.text import TextRegion
from core.ports.ocr import OcrOptions, OcrResult


class OcrEngineAdapter:
    def __init__(self, engine: Any, engine_name: str | None = None) -> None:
        self.engine = engine
        self.engine_name = engine_name or engine.__class__.__name__

    def recognize(self, image: ImageData, regions: list[TextRegion], options: OcrOptions) -> OcrResult:
        texts = self.engine.recognize(image.array, regions, options)
        recognized = [
            replace(region, text=str(texts[index] if index < len(texts) else region.text))
            for index, region in enumerate(regions)
        ]
        return OcrResult(regions=recognized, engine=self.engine_name)
