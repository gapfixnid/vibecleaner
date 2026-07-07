from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


QualityProfileName = Literal["speed", "balanced", "quality"]


@dataclass(frozen=True)
class QualityProfile:
    name: QualityProfileName = "balanced"

    @property
    def prefer_fast_models(self) -> bool:
        return self.name == "speed"

    @property
    def prefer_high_quality_models(self) -> bool:
        return self.name == "quality"
