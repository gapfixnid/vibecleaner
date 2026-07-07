from __future__ import annotations

from uuid import uuid4

from core.models.page import MangaPage
from core.state.project_state import ProjectState


class InMemoryProjectRepository:
    def __init__(self, state: ProjectState) -> None:
        self.state = state

    def list_pages(self) -> list[MangaPage]:
        with self.state.lock:
            return list(self.state.pages)

    def get_page(self, page_id: str) -> MangaPage:
        with self.state.lock:
            for page in self.state.pages:
                if page.id == page_id:
                    return page
        raise KeyError(f"Page not found: {page_id}")

    def save_page(self, page: MangaPage) -> None:
        with self.state.lock:
            for index, existing in enumerate(self.state.pages):
                if existing.id == page.id:
                    self.state.pages[index] = page
                    self.state.touch()
                    return
            self.state.pages.append(page)
            self.state.touch()

    def create_page(self, name: str, image_path: str) -> MangaPage:
        page = MangaPage(id=str(uuid4()), name=name, image_path=image_path)
        self.save_page(page)
        return page
