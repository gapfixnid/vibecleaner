import logging

import cv2
import numpy as np

from core.errors import PageImageLoadError
from core.models import MangaPage
from core.version import APP_NAME
from infrastructure.image.encoding import encode_thumbnail_bytes


logger = logging.getLogger(APP_NAME)


def load_cv_image(file_path: str) -> np.ndarray | None:
    """Load an image from disk without relying on OpenCV's path handling."""
    try:
        data = np.fromfile(file_path, dtype=np.uint8)
    except OSError:
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def ensure_original_thumbnail(page: MangaPage) -> bytes:
    cached = getattr(page, "_thumbnail_original_bytes", None)
    if cached is not None:
        return cached

    if getattr(page, "_loaded", True) is False and page.file_path:
        img = load_cv_image(page.file_path)
        if img is None:
            logger.error("Failed to load image for thumbnail: %s", page.file_path)
            raise PageImageLoadError(page.file_path)
    else:
        ensure_page_image(page)
        img = page.cv_image

    thumb_bytes = encode_thumbnail_bytes(img)
    page._thumbnail_original_bytes = thumb_bytes
    return thumb_bytes


def warm_original_thumbnail(page: MangaPage) -> None:
    try:
        ensure_original_thumbnail(page)
    except Exception as exc:
        logger.warning("Failed to generate thumbnail for %s: %s", page.file_path, exc)


def invalidate_page_caches(
    page: MangaPage,
    *,
    thumbnails: bool = False,
    layouts: bool = True,
    responses: bool = False,
) -> None:
    if layouts:
        page._bubble_layout_cache = {}
    if thumbnails:
        for attr in ("_thumbnail_original_bytes", "_thumbnail_inpainted_bytes"):
            if hasattr(page, attr):
                delattr(page, attr)
    if responses:
        for attr in (
            "_original_response_bytes",
            "_inpainted_response_bytes",
            "_preview_original_bytes",
            "_preview_inpainted_bytes",
        ):
            if hasattr(page, attr):
                delattr(page, attr)


def ensure_page_image(page: MangaPage) -> None:
    if getattr(page, "_loaded", True) is False or page.cv_image is None or page.cv_image.size == 0:
        cv_img = load_cv_image(page.file_path)
        if cv_img is None:
            logger.error("Failed to load page image: %s", page.file_path)
            raise PageImageLoadError(page.file_path)
        page.cv_image = cv_img
        page._width = cv_img.shape[1]
        page._height = cv_img.shape[0]
        page._loaded = True
