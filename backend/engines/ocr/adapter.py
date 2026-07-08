from __future__ import annotations

from dataclasses import replace
from typing import Any

from core.models.image import ImageData
from core.models.text import TextRegion
from core.ports.ocr import OcrOptions, OcrResult
from modules.utils.textblock import TextBlock


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
            recognized_blocks = self.engine.recognize_text(image.array, blocks, engine=options.engine)
            texts = [block.text for block in recognized_blocks]
        recognized = [
            replace(region, text=str(texts[index] if index < len(texts) else region.text))
            for index, region in enumerate(regions)
        ]
        return OcrResult(regions=recognized, engine=self.engine_name)
