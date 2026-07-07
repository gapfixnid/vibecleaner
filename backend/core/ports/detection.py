from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from core.models.image import ImageData
from core.models.text import TextRegion


@dataclass(frozen=True)
class DetectionOptions:
    model_name: str = "High Precision (FP32)"
    confidence_threshold: float = 0.3
    tiling_enabled: bool = True


@dataclass
class DetectionResult:
    regions: list[TextRegion] = field(default_factory=list)
    engine: str | None = None


class TextDetector(Protocol):
    def detect(self, image: ImageData, options: DetectionOptions) -> DetectionResult:
        ...
