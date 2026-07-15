from __future__ import annotations

from dataclasses import dataclass

from .geometry import Box


@dataclass
class TextRegion:
    box: Box
    text: str = ""
    confidence: float | None = None
    ocr_confidence: float | None = None
    bubble_id: str | None = None
