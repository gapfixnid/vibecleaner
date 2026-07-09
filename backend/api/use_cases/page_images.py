import io
import mimetypes
import os

from fastapi import HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from core.models import MangaPage
from core.version import APP_NAME
from infrastructure.image.encoding import (
    encode_jpeg_bytes,
    encode_png_bytes,
    encode_preview_jpeg_bytes,
    encode_thumbnail_bytes,
)
from infrastructure.image.loading import ensure_original_thumbnail, load_cv_image

import logging

logger = logging.getLogger(APP_NAME)

IMAGE_CACHE_HEADERS = {"Cache-Control": "public, max-age=3600"}


def _get_page_by_id(state, page_id: str) -> MangaPage:
    for page in state.pages:
        if page.page_id == page_id:
            return page
    raise HTTPException(status_code=404, detail="Page not found")


def _get_page_index_by_id(state, page_id: str) -> int:
    for idx, page in enumerate(state.pages):
        if page.page_id == page_id:
            return idx
    raise HTTPException(status_code=404, detail="Page not found")


def _resolve_page(state, page_id: str) -> MangaPage:
    if page_id.isdigit():
        idx = int(page_id)
        if 0 <= idx < len(state.pages):
            return state.pages[idx]
        raise HTTPException(status_code=404, detail="Page not found")
    return _get_page_by_id(state, page_id)


def _resolve_page_index(state, page_id: str) -> int:
    if page_id.isdigit():
        idx = int(page_id)
        if 0 <= idx < len(state.pages):
            return idx
        raise HTTPException(status_code=404, detail="Page not found")
    return _get_page_index_by_id(state, page_id)


def get_page_image_response(
    state,
    page_id: str,
    image_type: str = "original",
    thumbnail: bool = False,
    preview: bool = False,
):
    # Fast paths / source capture: hold the project lock only briefly.
    with state.lock:
        page = _resolve_page(state, page_id)
        page_idx = _resolve_page_index(state, page_id)

        if thumbnail:
            if image_type == "inpainted" and page.inpainted_image is not None:
                cached_bytes = getattr(page, "_thumbnail_inpainted_bytes", None)
                if cached_bytes is None:
                    cached_bytes = encode_thumbnail_bytes(page.inpainted_image)
                    page._thumbnail_inpainted_bytes = cached_bytes
            else:
                cached_bytes = ensure_original_thumbnail(page)
            return StreamingResponse(
                io.BytesIO(cached_bytes),
                media_type="image/png",
                headers=IMAGE_CACHE_HEADERS,
            )

        if not preview and image_type == "original" and page.file_path and os.path.exists(page.file_path):
            media_type = mimetypes.guess_type(page.file_path)[0] or "application/octet-stream"
            return FileResponse(
                page.file_path,
                media_type=media_type,
                headers=IMAGE_CACHE_HEADERS,
            )

        response_kind = "inpainted" if (image_type == "inpainted" and page.inpainted_image is not None) else "original"
        if preview:
            cache_attr = f"_preview_{response_kind}_bytes"
            media_type = "image/jpeg"
        else:
            cache_attr = f"_{response_kind}_response_bytes"
            media_type = "image/jpeg" if response_kind == "inpainted" else "image/png"

        cached_bytes = getattr(page, cache_attr, None)
        if cached_bytes is not None:
            return StreamingResponse(io.BytesIO(cached_bytes), media_type=media_type, headers=IMAGE_CACHE_HEADERS)

        if response_kind == "inpainted":
            source_img = page.inpainted_image
            needs_disk_load = False
        else:
            loaded = getattr(page, "_loaded", True) and page.cv_image is not None and page.cv_image.size > 0
            source_img = page.cv_image if loaded else None
            needs_disk_load = not loaded
        load_path = page.file_path

    # Disk load + encode can be expensive, so do it outside the lock.
    if needs_disk_load:
        source_img = load_cv_image(load_path)
        if source_img is None:
            logger.error("Failed to load page image: %s", load_path)
            raise HTTPException(status_code=500, detail="Failed to load page image")

    if preview:
        encoded = encode_preview_jpeg_bytes(source_img)
    else:
        encoded = encode_jpeg_bytes(source_img) if response_kind == "inpainted" else encode_png_bytes(source_img)

    # Store cache best-effort after confirming the page is still the same object.
    with state.lock:
        if 0 <= page_idx < len(state.pages) and state.pages[page_idx] is page:
            setattr(page, cache_attr, encoded)
            if needs_disk_load and response_kind == "original" and (page.cv_image is None or page.cv_image.size == 0):
                page.cv_image = source_img
                page._width = source_img.shape[1]
                page._height = source_img.shape[0]
                page._loaded = True

    return StreamingResponse(io.BytesIO(encoded), media_type=media_type, headers=IMAGE_CACHE_HEADERS)
