from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any

from PIL import Image

from .loading import load_cv_image


MAX_IMAGE_BYTES = 200 * 1024 * 1024
MAX_IMAGE_PIXELS = 100_000_000
MAX_IMAGE_DIMENSION = 30_000
WARNING_MEMORY_BYTES = 512 * 1024 * 1024


@dataclass(frozen=True)
class ImportIssue:
    path: str
    code: str
    reason: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "code": self.code,
            "reason": self.reason,
            "details": dict(self.details),
        }


@dataclass
class ImportReport:
    accepted: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[ImportIssue] = field(default_factory=list)
    warnings: list[ImportIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": list(self.accepted),
            "rejected": [issue.to_dict() for issue in self.rejected],
            "warnings": [issue.to_dict() for issue in self.warnings],
        }


def validate_image_for_import(path: str) -> tuple[dict[str, Any] | None, list[ImportIssue]]:
    """Validate both metadata and the same OpenCV decoder used at runtime."""
    warnings: list[ImportIssue] = []
    try:
        file_size = os.path.getsize(path)
    except OSError as exc:
        return None, [ImportIssue(path, "FILE_UNREADABLE", str(exc))]
    if file_size > MAX_IMAGE_BYTES:
        return None, [ImportIssue(path, "FILE_TOO_LARGE", "Image file exceeds the import limit.", {"bytes": file_size})]

    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            width, height = image.size
            format_name = image.format or "unknown"
    except Exception as exc:
        return None, [ImportIssue(path, "IMAGE_DECODE_FAILED", str(exc))]

    pixels = int(width) * int(height)
    if pixels > MAX_IMAGE_PIXELS:
        return None, [ImportIssue(path, "PIXEL_COUNT_TOO_LARGE", "Image pixel count exceeds the import limit.", {"width": width, "height": height, "pixels": pixels})]
    if max(width, height) > MAX_IMAGE_DIMENSION:
        return None, [ImportIssue(path, "IMAGE_DIMENSION_TOO_LARGE", "Image dimension exceeds the import limit.", {"width": width, "height": height})]

    estimated_memory = pixels * 3 * 4
    if estimated_memory > WARNING_MEMORY_BYTES:
        warnings.append(ImportIssue(path, "HIGH_MEMORY_IMAGE", "Image may require substantial working memory.", {"estimated_memory_bytes": estimated_memory}))

    decoded = load_cv_image(path)
    if decoded is None or decoded.size == 0:
        return None, [ImportIssue(path, "RUNTIME_DECODER_FAILED", "The OpenCV runtime decoder could not load this image.")]

    return {
        "path": path,
        "width": width,
        "height": height,
        "format": format_name,
        "file_size_bytes": file_size,
        "estimated_memory_bytes": estimated_memory,
    }, warnings
