from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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