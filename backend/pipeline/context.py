from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from ..core.models.image import ImageData
from ..core.models.page import MangaPage
from .provenance import ProvenanceTrace


@dataclass
class PipelineContext:
    page_id: str
    page: MangaPage
    image: ImageData
    settings: Any
    artifacts: dict[str, Any] = field(default_factory=dict)
    provenance: ProvenanceTrace = field(default_factory=ProvenanceTrace)


@dataclass(frozen=True)
class PipelineSnapshot:
    """Immutable stage input captured at a single page revision."""

    page_id: str
    project_generation: int
    visual_revision: int
    image_visual_revision: int
    bubbles: tuple[Any, ...]


@dataclass(frozen=True)
class StageOutput:
    """Named output produced by a stage and consumed at a join/commit point."""

    stage: str
    values: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))
