from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Any


@dataclass
class ProjectState:
    pages: list[Any] = field(default_factory=list)
    current_page_idx: int = -1
    revision: int = 0
    project_extensions: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.lock = RLock()

    def touch(self) -> int:
        with self.lock:
            self.revision += 1
            return self.revision
