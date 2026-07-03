from threading import RLock
from typing import List

from app.models import MangaPage


class ProjectState:
    def __init__(self):
        self.pages: List[MangaPage] = []
        self.current_page_idx: int = -1
        self.revision: int = 0
        self.lock = RLock()

    def touch(self) -> int:
        with self.lock:
            self.revision += 1
            return self.revision


state = ProjectState()
