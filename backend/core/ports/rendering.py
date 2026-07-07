from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from core.models.image import ImageData
from core.models.page import Bubble


@dataclass(frozen=True)
class RenderOptions:
    min_font_size: float = 8.0
    max_font_size: float = 32.0
    default_font_size: float = 16.0
    font_family: str | None = None


@dataclass
class RenderResult:
    image: ImageData
    engine: str | None = None


class Renderer(Protocol):
    def render(
        self,
        image: ImageData,
        bubbles: list[Bubble],
        options: RenderOptions,
    ) -> RenderResult:
        ...
