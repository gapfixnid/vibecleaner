from __future__ import annotations

from typing import Any

from ...core.models.image import ImageData
from ...core.models.page import Bubble
from ...core.ports.rendering import RenderOptions, RenderResult


class RenderingEngineAdapter:
    def __init__(self, engine: Any, engine_name: str | None = None) -> None:
        self.engine = engine
        self.engine_name = engine_name or engine.__class__.__name__

    def render(
        self,
        image: ImageData,
        bubbles: list[Bubble],
        options: RenderOptions,
    ) -> RenderResult:
        output = self.engine.render(image.array, bubbles, options)
        if output is image.array:
            return RenderResult(image=image, engine=self.engine_name)
        return RenderResult(
            image=ImageData(array=output, mode=image.mode, path=image.path),
            engine=self.engine_name,
        )