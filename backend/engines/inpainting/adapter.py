from __future__ import annotations

from typing import Any

from core.models.image import ImageData
from core.ports.inpainting import InpaintOptions, InpaintRegion, InpaintResult


class InpaintingEngineAdapter:
    def __init__(self, engine: Any, engine_name: str | None = None) -> None:
        self.engine = engine
        self.engine_name = engine_name or engine.__class__.__name__

    def inpaint(
        self,
        image: ImageData,
        regions: list[InpaintRegion],
        options: InpaintOptions,
    ) -> InpaintResult:
        boxes = [[r.box.x1, r.box.y1, r.box.x2, r.box.y2] for r in regions]
        bubble_boxes = [
            [r.bubble_box.x1, r.bubble_box.y1, r.bubble_box.x2, r.bubble_box.y2]
            for r in regions
            if r.bubble_box is not None
        ]
        output = self.engine.inpaint(
            image.array,
            boxes,
            bubble_boxes=bubble_boxes or None,
            protect_edges=False,
            engine=options.engine,
            mask_dilation=options.mask_dilation,
            clip_to_bubble=options.clip_to_bubble,
        )
        if output is image.array:
            return InpaintResult(image=image, engine=self.engine_name)
        return InpaintResult(
            image=ImageData(array=output, mode=image.mode, path=image.path),
            engine=self.engine_name,
        )
