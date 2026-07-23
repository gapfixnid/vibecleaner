from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Any


@dataclass
class ProjectState:
    pages: list[Any] = field(default_factory=list)
    current_page_idx: int = -1
    project_generation: int = 0
    content_revision: int = 0
    project_extensions: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.lock = RLock()

    @property
    def revision(self) -> int:
        """Compatibility alias for persisted-content revision."""
        return self.content_revision

    @revision.setter
    def revision(self, value: int) -> None:
        self.content_revision = int(value)

    def touch(self) -> int:
        with self.lock:
            self.content_revision += 1
            return self.content_revision

    def replace_project(self) -> tuple[int, int]:
        """Record a new/load/replace boundary independently from page edits."""
        with self.lock:
            self.project_generation += 1
            self.content_revision += 1
            return self.project_generation, self.content_revision
