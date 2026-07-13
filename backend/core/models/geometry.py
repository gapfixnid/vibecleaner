from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class Rect:
    """Axis-aligned rectangle in x/y/width/height form (float pixels)."""

    x: float
    y: float
    width: float
    height: float

    @classmethod
    def from_xyxy(cls, x1: float, y1: float, x2: float, y2: float) -> "Rect":
        return cls(x=x1, y=y1, width=x2 - x1, height=y2 - y1)

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    def to_xyxy(self) -> list[float]:
        return [self.x, self.y, self.right, self.bottom]

    def to_xywh(self) -> list[float]:
        return [self.x, self.y, self.width, self.height]

    def united(self, other: "Rect") -> "Rect":
        return Rect.from_xyxy(
            min(self.x, other.x),
            min(self.y, other.y),
            max(self.right, other.right),
            max(self.bottom, other.bottom),
        )


@dataclass(frozen=True)
class Box:
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return max(0, self.x2 - self.x1)

    @property
    def height(self) -> int:
        return max(0, self.y2 - self.y1)

    def is_valid(self) -> bool:
        return self.x2 > self.x1 and self.y2 > self.y1

    def clamp(self, width: int, height: int) -> "Box":
        return Box(
            x1=max(0, min(width, self.x1)),
            y1=max(0, min(height, self.y1)),
            x2=max(0, min(width, self.x2)),
            y2=max(0, min(height, self.y2)),
        )
