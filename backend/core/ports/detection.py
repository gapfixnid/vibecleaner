from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..models.image import ImageData
from ..models.text import TextRegion


@dataclass(frozen=True)
class DetectionOptions:
    model_name: str = "High Precision (FP32)"
    confidence_threshold: float = 0.3
    tiling_enabled: bool = True
    bubbles_only: bool = False
    line_merge_sensitivity: float = 1.2
    smart_direction: bool = True
    text_direction_override: str = "auto"


@dataclass
class DetectionResult:
    regions: list[TextRegion] = field(default_factory=list)
    engine: str | None = None


class TextDetector(Protocol):
    def detect(self, image: ImageData, options: DetectionOptions) -> DetectionResult:
        ...