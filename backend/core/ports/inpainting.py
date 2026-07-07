from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from core.models.geometry import Box
from core.models.image import ImageData


@dataclass(frozen=True)
class InpaintRegion:
    box: Box
    bubble_box: Box | None = None


@dataclass(frozen=True)
class InpaintOptions:
    engine: str = "lama"
    mask_dilation: int = 3
    clip_to_bubble: bool = True


@dataclass
class InpaintResult:
    image: ImageData
    engine: str | None = None


class Inpainter(Protocol):
    def inpaint(
        self,
        image: ImageData,
        regions: list[InpaintRegion],
        options: InpaintOptions,
    ) -> InpaintResult:
        ...
