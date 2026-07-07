from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock

from core.models.page import MangaPage


@dataclass
class ProjectState:
    pages: list[MangaPage] = field(default_factory=list)
    current_page_idx: int = -1
    revision: int = 0

    def __post_init__(self) -> None:
        self.lock = RLock()

    def touch(self) -> int:
        with self.lock:
            self.revision += 1
            return self.revision
