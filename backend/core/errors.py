"""Domain errors shared across layers.

Lower layers (infrastructure, pipeline, engines) raise these instead of
HTTP exceptions; the API layer maps them to HTTP responses in main.py.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for backend domain errors."""


class PageNotFoundError(DomainError):
    def __init__(self, page_id: str | None = None) -> None:
        super().__init__("Page not found" if page_id is None else f"Page not found: {page_id}")
        self.page_id = page_id


class PageImageLoadError(DomainError):
    def __init__(self, file_path: str | None = None) -> None:
        super().__init__(
            "Failed to load page image" if file_path is None else f"Failed to load page image: {file_path}"
        )
        self.file_path = file_path
