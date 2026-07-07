from __future__ import annotations

from typing import Protocol

from core.models.page import MangaPage


class ProjectRepository(Protocol):
    def list_pages(self) -> list[MangaPage]:
        ...

    def get_page(self, page_id: str) -> MangaPage:
        ...

    def save_page(self, page: MangaPage) -> None:
        ...
