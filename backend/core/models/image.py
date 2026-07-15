from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ImageData:
    array: Any
    mode: str = "BGR"
    path: str | None = None
    explicit_width: int | None = None
    explicit_height: int | None = None

    @property
    def width(self) -> int:
        if self.explicit_width is not None:
            return self.explicit_width
        shape = getattr(self.array, "shape", None)
        if shape and len(shape) >= 2:
            return int(shape[1])
        return 0

    @property
    def height(self) -> int:
        if self.explicit_height is not None:
            return self.explicit_height
        shape = getattr(self.array, "shape", None)
        if shape and len(shape) >= 2:
            return int(shape[0])
        return 0
