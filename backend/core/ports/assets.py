from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class FontAsset:
    path: str | None
    family: str | None = None


@dataclass(frozen=True)
class ModelAsset:
    path: str
    model_id: str


class AssetStore(Protocol):
    def resolve_font(self, font_name: str | None) -> FontAsset:
        ...

    def resolve_model(self, model_id: str) -> ModelAsset:
        ...
