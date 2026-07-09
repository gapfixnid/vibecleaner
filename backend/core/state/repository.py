from __future__ import annotations

from ..models.page import MangaPage
from .project_state import ProjectState


class InMemoryProjectRepository:
    def __init__(self, state: ProjectState) -> None:
        self.state = state

    def list_pages(self) -> list[MangaPage]:
        with self.state.lock:
            return list(self.state.pages)

    def get_page(self, page_id: str) -> MangaPage:
        with self.state.lock:
            for page in self.state.pages:
                if page.page_id == page_id:
                    return page
        raise KeyError(f"Page not found: {page_id}")

    def save_page(self, page: MangaPage) -> None:
        with self.state.lock:
            for index, existing in enumerate(self.state.pages):
                if existing.page_id == page.page_id:
                    self.state.pages[index] = page
                    self.state.touch()
                    return
            self.state.pages.append(page)
            self.state.touch()

    def create_page(self, file_path: str, display_name: str | None = None) -> MangaPage:
        page = MangaPage(file_path=file_path, display_name=display_name)
        self.save_page(page)
        return page