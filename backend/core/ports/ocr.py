from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from core.models.image import ImageData
from core.models.text import TextRegion


@dataclass(frozen=True)
class OcrOptions:
    engine: str = "balanced"
    padding: int = 8
    crop_scale: float = 1.5


@dataclass
class OcrResult:
    regions: list[TextRegion] = field(default_factory=list)
    engine: str | None = None


class OcrEngine(Protocol):
    def recognize(
        self,
        image: ImageData,
        regions: list[TextRegion],
        options: OcrOptions,
    ) -> OcrResult:
        ...
