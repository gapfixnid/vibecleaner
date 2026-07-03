import os
import cv2
import io
import mimetypes
import numpy as np
from functools import lru_cache
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Form
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from PIL import Image

from app.models import MangaPage, TextBubble
from modules.utils.textblock import TextBlock
from modules.config import config
from services.auto_typeset_pipeline import auto_typeset_pipeline, bubble_clip_boxes, inpaint_boxes
from core import (
    state,
    job_manager,
    encode_jpeg_bytes,
    encode_png_bytes,
    encode_preview_jpeg_bytes,
    encode_thumbnail_bytes,
    ensure_page_image,
    ensure_original_thumbnail,
    invalidate_page_caches,
    load_cv_image,
    logger,
    render_service,
    detection_service,
    translation_service,
    inpainting_service,
    export_service,
)

router = APIRouter()

IMAGE_CACHE_HEADERS = {"Cache-Control": "public, max-age=3600"}


def _validate_page_idx(page_idx: int) -> None:
    if page_idx < 0 or page_idx >= len(state.pages):
        raise HTTPException(status_code=404, detail="Page not found")


def _get_page_by_id(page_id: str) -> MangaPage:
    for p in state.pages:
        if p.page_id == page_id:
            return p
    raise HTTPException(status_code=404, detail="Page not found")


def _get_page_index_by_id(page_id: str) -> int:
    for idx, p in enumerate(state.pages):
        if p.page_id == page_id:
            return idx
    raise HTTPException(status_code=404, detail="Page not found")


def _resolve_page(page_id: str) -> MangaPage:
    if page_id.isdigit():
        idx = int(page_id)
        if 0 <= idx < len(state.pages):
            return state.pages[idx]
        raise HTTPException(status_code=404, detail="Page not found")
    return _get_page_by_id(page_id)


def _resolve_page_index(page_id: str) -> int:
    if page_id.isdigit():
        idx = int(page_id)
        if 0 <= idx < len(state.pages):
            return idx
        raise HTTPException(status_code=404, detail="Page not found")
    return _get_page_index_by_id(page_id)


def _ensure_project_revision(start_revision: int) -> None:
    if state.revision != start_revision:
        raise RuntimeError("Project changed while the operation was running. Please retry.")


def _layout_cache_key(bubble: TextBubble) -> tuple:
    box = bubble.box
    text_box = bubble.text_box
    return (
        bubble.id,
        round(box.x(), 2),
        round(box.y(), 2),
        round(box.width(), 2),
        round(box.height(), 2),
        tuple(round(v, 2) for v in bubble.source_xyxy()) if text_box is not None else None,
        bubble.text,
        bubble.translated,
        bubble.font_family,
        bubble.font_size,
        bubble.bold,
        bubble.italic,
        bubble.color,
        bubble.alignment,
    )


def _compute_bubble_layout(bubble: TextBubble, image) -> dict:
    layout = render_service.get_layout_for_bubble(
        bubble.translated or bubble.text or "",
        bubble,
        image=image,
        font_family=bubble.font_family or None,
    )
    return {
        "font_size": bubble.font_size if bubble.font_size > 0 else int(layout.font.pointSizeF()),
        "lines": [
            {
                "text": line.text,
                "x": line.x,
                "y": line.y,
                "width": line.width,
                "height": line.height
            }
            for line in layout.line_layouts
        ],
    }

class BubbleUpdateSchema(BaseModel):
    id: int
    x: float
    y: float
    width: float
    height: float
    text: str
    translated: str
    font_family: str
    font_size: int
    bold: bool
    italic: bool
    color: str
    alignment: str


class TranslateBatchRequest(BaseModel):
    page_indices: Optional[List[int]] = None
    page_ids: Optional[List[str]] = None

@router.get("/api/pages")
def get_pages():
    with state.lock:
        pages_list = []
        for idx, p in enumerate(state.pages):
            w = getattr(p, "_width", 0)
            h = getattr(p, "_height", 0)
            if w == 0 or h == 0:
                if p.cv_image is not None and p.cv_image.size > 0:
                    h, w = p.cv_image.shape[:2]
                else:
                    try:
                        with Image.open(p.file_path) as img:
                            w, h = img.size
                        p._width = w
                        p._height = h
                    except Exception:
                        w, h = 100, 100
            pages_list.append({
                "page_id": p.page_id,
                "index": idx,
                "file_path": p.file_path,
                "filename": p.display_name or os.path.basename(p.file_path),
                "width": w,
                "height": h,
                "bubble_count": len(p.bubbles),
                "translated_count": sum(1 for b in p.bubbles if (b.translated or "").strip()),
                "has_inpaint": p.inpainted_image is not None
            })
        return {"pages": pages_list, "current_index": state.current_page_idx}

@router.post("/api/pages/select")
def select_page(index: Optional[int] = Form(None), page_id: Optional[str] = Form(None)):
    with state.lock:
        if page_id is not None:
            index = _get_page_index_by_id(page_id)
        elif index is None:
            raise HTTPException(status_code=400, detail="Either index or page_id must be provided")

        if index < 0 or index >= len(state.pages):
            raise HTTPException(status_code=404, detail="Page index out of bounds")
        state.current_page_idx = index
        return {"status": "ok", "current_index": state.current_page_idx}

def _resolve_indices_from_request(req: TranslateBatchRequest) -> List[int]:
    indices = []
    if req.page_ids:
        for pid in req.page_ids:
            try:
                indices.append(_resolve_page_index(pid))
            except HTTPException:
                pass
    if req.page_indices:
        for idx in req.page_indices:
            if 0 <= idx < len(state.pages) and idx not in indices:
                indices.append(idx)
    return indices

@router.post("/api/pages/{page_id}/rename")
def rename_page(page_id: str, name: str = Form(...)):
    """Rename a page's display name (stem only; the extension is preserved)."""
    cleaned = (name or "").strip().replace("/", "").replace("\\", "")
    if not cleaned:
        raise HTTPException(status_code=400, detail="Name must not be empty")

    with state.lock:
        page = _resolve_page(page_id)
        current = page.display_name or os.path.basename(page.file_path)
        ext = os.path.splitext(current)[1]
        page.display_name = f"{cleaned}{ext}"
        state.touch()
        return {"status": "ok", "filename": page.display_name}


def _clone_page(source: MangaPage) -> MangaPage:
    """Create a deep clone of a MangaPage (images copied, bubbles detached)."""
    ensure_page_image(source)
    clone = MangaPage(
        file_path=source.file_path,
        cv_image=source.cv_image.copy(),
        inpainted_image=source.inpainted_image.copy() if source.inpainted_image is not None else None,
        bubbles=[bubble.without_item() for bubble in source.bubbles],
        bubble_counter=source.bubble_counter,
    )
    clone._width = getattr(source, "_width", 0)
    clone._height = getattr(source, "_height", 0)
    clone._loaded = getattr(source, "_loaded", True)
    if getattr(source, "_thumbnail_original_bytes", None) is not None:
        clone._thumbnail_original_bytes = source._thumbnail_original_bytes
    return clone


@router.post("/api/pages/duplicate")
def duplicate_page(index: Optional[int] = Form(None), page_id: Optional[str] = Form(None)):
    with state.lock:
        if page_id is not None:
            index = _resolve_page_index(page_id)
        elif index is None:
            raise HTTPException(status_code=400, detail="Either index or page_id must be provided")
        if index < 0 or index >= len(state.pages):
            raise HTTPException(status_code=404, detail="Page index out of bounds")
        state.pages.insert(index + 1, _clone_page(state.pages[index]))
        state.current_page_idx = index + 1
        state.touch()
        return {"status": "ok", "current_index": state.current_page_idx}


@router.post("/api/pages/duplicate-batch")
def duplicate_page_batch(req: TranslateBatchRequest):
    """Duplicate multiple pages in one call."""
    with state.lock:
        valid_indices = sorted(set(_resolve_indices_from_request(req)))
        if not valid_indices:
            raise HTTPException(status_code=400, detail="No valid pages to duplicate")
        for idx in sorted(valid_indices, reverse=True):
            state.pages.insert(idx + 1, _clone_page(state.pages[idx]))
        state.current_page_idx = valid_indices[0] + 1
        state.touch()
        return {
            "status": "ok",
            "current_index": state.current_page_idx,
            "duplicated_count": len(valid_indices),
        }

def _clamp_current_index() -> None:
    """Clamp current_page_idx to valid range after pages are removed."""
    if state.current_page_idx >= len(state.pages):
        state.current_page_idx = len(state.pages) - 1


@router.post("/api/pages/delete")
def delete_page(index: Optional[int] = Form(None), page_id: Optional[str] = Form(None)):
    with state.lock:
        if page_id is not None:
            index = _resolve_page_index(page_id)
        elif index is None:
            raise HTTPException(status_code=400, detail="Either index or page_id must be provided")
        if index < 0 or index >= len(state.pages):
            raise HTTPException(status_code=404, detail="Page index out of bounds")
        state.pages.pop(index)
        _clamp_current_index()
        state.touch()
        return {"status": "ok", "current_index": state.current_page_idx}


@router.post("/api/pages/delete-batch")
def delete_page_batch(req: TranslateBatchRequest):
    """Delete multiple pages in one call."""
    with state.lock:
        valid_indices = _resolve_indices_from_request(req)
        if not valid_indices:
            raise HTTPException(status_code=400, detail="No valid pages to delete")
        for idx in sorted(set(valid_indices), reverse=True):
            state.pages.pop(idx)
        _clamp_current_index()
        state.touch()
        return {"status": "ok", "current_index": state.current_page_idx, "deleted_count": len(valid_indices)}

@router.post("/api/pages/reorder")
def reorder_pages(from_index: int = Form(...), to_index: int = Form(...)):
    with state.lock:
        if from_index < 0 or from_index >= len(state.pages) or to_index < 0 or to_index >= len(state.pages):
            raise HTTPException(status_code=404, detail="Indices out of bounds")
        page = state.pages.pop(from_index)
        state.pages.insert(to_index, page)
        if state.current_page_idx == from_index:
            state.current_page_idx = to_index
        elif from_index < state.current_page_idx <= to_index:
            state.current_page_idx -= 1
        elif to_index <= state.current_page_idx < from_index:
            state.current_page_idx += 1
        state.touch()
        return {"status": "ok", "current_index": state.current_page_idx}

@router.get("/api/pages/{page_id}/image")
def get_page_image(page_id: str, type: str = "original", thumbnail: bool = False, preview: bool = False):
    # --- Phase 1: fast paths / capture source, holding the lock only briefly ---
    with state.lock:
        page = _resolve_page(page_id)
        page_idx = _resolve_page_index(page_id)

        if thumbnail:
            if type == "inpainted" and page.inpainted_image is not None:
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

        if not preview and type == "original" and page.file_path and os.path.exists(page.file_path):
            media_type = mimetypes.guess_type(page.file_path)[0] or "application/octet-stream"
            return FileResponse(
                page.file_path,
                media_type=media_type,
                headers=IMAGE_CACHE_HEADERS,
            )

        response_kind = "inpainted" if (type == "inpainted" and page.inpainted_image is not None) else "original"
        if preview:
            cache_attr = f"_preview_{response_kind}_bytes"
            media_type = "image/jpeg"
        else:
            cache_attr = f"_{response_kind}_response_bytes"
            media_type = "image/jpeg" if response_kind == "inpainted" else "image/png"

        cached_bytes = getattr(page, cache_attr, None)
        if cached_bytes is not None:
            return StreamingResponse(io.BytesIO(cached_bytes), media_type=media_type, headers=IMAGE_CACHE_HEADERS)

        # Cache miss: capture the source image reference; defer disk load + encode
        # until after releasing the lock so heavy work never blocks other requests.
        if response_kind == "inpainted":
            source_img = page.inpainted_image
            needs_disk_load = False
        else:
            loaded = getattr(page, "_loaded", True) and page.cv_image is not None and page.cv_image.size > 0
            source_img = page.cv_image if loaded else None
            needs_disk_load = not loaded
        load_path = page.file_path

    # --- Phase 2: load (if needed) + encode OUTSIDE the lock ---
    if needs_disk_load:
        source_img = load_cv_image(load_path)
        if source_img is None:
            logger.error("Failed to load page image: %s", load_path)
            raise HTTPException(status_code=500, detail="Failed to load page image")

    if preview:
        encoded = encode_preview_jpeg_bytes(source_img)
    else:
        encoded = encode_jpeg_bytes(source_img) if response_kind == "inpainted" else encode_png_bytes(source_img)

    # --- Phase 3: store the cache under the lock (best-effort; re-validate page) ---
    with state.lock:
        if 0 <= page_idx < len(state.pages) and state.pages[page_idx] is page:
            setattr(page, cache_attr, encoded)
            if needs_disk_load and response_kind == "original" and (page.cv_image is None or page.cv_image.size == 0):
                page.cv_image = source_img
                page._width = source_img.shape[1]
                page._height = source_img.shape[0]
                page._loaded = True

    return StreamingResponse(io.BytesIO(encoded), media_type=media_type, headers=IMAGE_CACHE_HEADERS)

@router.get("/api/pages/{page_id}/bubbles")
def get_bubbles(page_id: str):
    with state.lock:
        page = _resolve_page(page_id)
        loaded = getattr(page, "_loaded", True) and page.cv_image is not None and page.cv_image.size > 0
        source_img = page.cv_image if loaded else None
        load_path = page.file_path
        bubbles_snapshot = [bubble.without_item() for bubble in page.bubbles]
        layout_cache = getattr(page, "_bubble_layout_cache", None)
        if layout_cache is None:
            layout_cache = {}
            page._bubble_layout_cache = layout_cache
        cached_layouts = {
            bubble.id: layout_cache.get(_layout_cache_key(bubble))
            for bubble in bubbles_snapshot
        }

    if source_img is None:
        source_img = load_cv_image(load_path)
        if source_img is None:
            logger.error("Failed to load page image for bubble layout: %s", load_path)
            raise HTTPException(status_code=500, detail="Failed to load page image")

    computed_layouts = {}
    bubbles_list = []
    for b in bubbles_snapshot:
        cached_layout = cached_layouts.get(b.id)
        if cached_layout is None:
            cached_layout = _compute_bubble_layout(b, source_img)
            computed_layouts[_layout_cache_key(b)] = cached_layout

        bubbles_list.append({
            "id": b.id,
            "x": b.box.x(),
            "y": b.box.y(),
            "width": b.box.width(),
            "height": b.box.height(),
            "text": b.text,
            "translated": b.translated,
            "font_family": b.font_family,
            "font_size": b.font_size,
            "computed_font_size": cached_layout["font_size"],
            "bold": b.bold,
            "italic": b.italic,
            "color": b.color,
            "alignment": b.alignment,
            "text_class": b.text_class,
            "lines": cached_layout["lines"]
        })

    with state.lock:
        if any(existing is page for existing in state.pages):
            if not loaded and (page.cv_image is None or page.cv_image.size == 0):
                page.cv_image = source_img
                page._width = source_img.shape[1]
                page._height = source_img.shape[0]
                page._loaded = True
            if computed_layouts:
                layout_cache = getattr(page, "_bubble_layout_cache", None)
                if layout_cache is None:
                    layout_cache = {}
                    page._bubble_layout_cache = layout_cache
                layout_cache.update(computed_layouts)

    return {"bubbles": bubbles_list}

@router.post("/api/pages/{page_id}/bubbles")
def update_bubbles(page_id: str, bubbles: List[BubbleUpdateSchema]):
    with state.lock:
        page = _resolve_page(page_id)

        from PySide6.QtCore import QRectF

        updated_bubbles = []
        for b_schema in bubbles:
            existing = next((eb for eb in page.bubbles if eb.id == b_schema.id), None)
            text_box = existing.text_box if existing else None
            text_class = existing.text_class if existing else "text_bubble"

            tb = TextBubble(
                id=b_schema.id,
                box=QRectF(b_schema.x, b_schema.y, b_schema.width, b_schema.height),
                text=b_schema.text,
                translated=b_schema.translated,
                text_box=text_box,
                text_class=text_class,
                font_family=b_schema.font_family,
                font_size=b_schema.font_size,
                bold=b_schema.bold,
                italic=b_schema.italic,
                color=b_schema.color,
                alignment=b_schema.alignment
            )
            updated_bubbles.append(tb)

        page.bubbles = updated_bubbles
        # Keep the counter monotonic so deleting bubbles cannot cause a
        # future generated bubble to reuse an old id.
        page.bubble_counter = max(page.bubble_counter, max((b.id for b in page.bubbles), default=0))
        invalidate_page_caches(page)
        state.touch()
        return {"status": "ok"}

@router.post("/api/pages/{page_id}/bubbles/{bubble_id}/ocr")
def re_ocr_bubble(page_id: str, bubble_id: int):
    with state.lock:
        page = _resolve_page(page_id)
        ensure_page_image(page)

        bubble = next((b for b in page.bubbles if b.id == bubble_id), None)
        if not bubble:
            raise HTTPException(status_code=404, detail="Bubble not found")
        image = page.cv_image.copy()
        box = bubble.box

    x1, y1 = int(box.x()), int(box.y())
    x2, y2 = int(box.x() + box.width()), int(box.y() + box.height())
    tb_block = TextBlock(text_bbox=np.array([x1, y1, x2, y2]))
    try:
        detection_service.recognize_single_block(image, tb_block, lang=config.source_language)
    except Exception as e:
        logger.warning("Failed to re-OCR bubble %s: %s", bubble_id, e)

    with state.lock:
        page = _resolve_page(page_id)
        bubble = next((b for b in page.bubbles if b.id == bubble_id), None)
        if not bubble:
            raise HTTPException(status_code=404, detail="Bubble not found")
        bubble.text = tb_block.text
        invalidate_page_caches(page)
        state.touch()
        return {"status": "ok", "text": bubble.text}

@router.post("/api/pages/{page_id}/bubbles/{bubble_id}/translate")
def translate_single_bubble(page_id: str, bubble_id: int):
    with state.lock:
        page = _resolve_page(page_id)
        page_idx = _resolve_page_index(page_id)
        if not any(b.id == bubble_id for b in page.bubbles):
            raise HTTPException(status_code=404, detail="Bubble not found")

    return job_manager.start(
        "translate-bubble",
        page_idx,
        f"translate-bubble:{page_id}:{bubble_id}",
        lambda job: _translate_single_bubble_job(job, page_id, bubble_id),
    )

@router.post("/api/pages/{page_id}/bubbles/{bubble_id}/inpaint")
def inpaint_single_bubble(page_id: str, bubble_id: int):
    with state.lock:
        page = _resolve_page(page_id)
        page_idx = _resolve_page_index(page_id)
        ensure_page_image(page)
        bubble = next((b for b in page.bubbles if b.id == bubble_id), None)
        if not bubble:
            raise HTTPException(status_code=404, detail="Bubble not found")

    return job_manager.start(
        "inpaint-bubble",
        page_idx,
        f"inpaint-bubble:{page_id}:{bubble_id}",
        lambda job: _inpaint_single_bubble_job(job, page_id, bubble_id),
    )

@router.post("/api/pages/{page_id}/inpaint")
def run_inpaint(page_id: str):
    with state.lock:
        page_idx = _resolve_page_index(page_id)
    return job_manager.start("inpaint", page_idx, f"inpaint:{page_id}", lambda job: _inpaint_job(job, page_id))

@router.post("/api/pages/{page_id}/translate-all")
def run_translate_all(page_id: str):
    with state.lock:
        page_idx = _resolve_page_index(page_id)
    return job_manager.start(
        "auto-typeset",
        page_idx,
        f"auto-typeset:{page_id}",
        lambda job: auto_typeset_pipeline.run_page(job, page_id, show_progress=True),
    )

@router.post("/api/pages/translate-batch")
def run_translate_batch(req: TranslateBatchRequest):
    """Translate multiple pages as a single batch job."""
    with state.lock:
        valid_indices = _resolve_indices_from_request(req)
        if not valid_indices:
            raise HTTPException(status_code=400, detail="No valid pages to translate")
        page_ids = [state.pages[idx].page_id for idx in valid_indices]
        first_idx = valid_indices[0]

    key = f"auto-typeset-batch:{','.join(page_ids)}"
    return job_manager.start(
        "auto-typeset-batch",
        first_idx,
        key,
        lambda job: auto_typeset_pipeline.run_batch(job, page_ids),
    )


@router.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    job = job_manager.cancel(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _translate_single_bubble_job(job: dict, page_id: str, bubble_id: int):
    with state.lock:
        page_idx = _resolve_page_index(page_id)
        page = state.pages[page_idx]
        ensure_page_image(page)
        bubble = next((b for b in page.bubbles if b.id == bubble_id), None)
        if not bubble:
            raise RuntimeError("Bubble not found")
        start_revision = state.revision
        image = page.cv_image.copy()
        bubble_snapshot = bubble.without_item()

    job_manager.ensure_not_cancelled(job)
    job_manager.update(job, progress=30, message="Translating selected bubble")
    tb_block = TextBlock(
        text_bbox=np.array(bubble_snapshot.source_xyxy()).astype(np.int32),
        text=bubble_snapshot.text
    )
    translation_service.translate_blocks([tb_block], config.source_language, config.target_language, image)
    job_manager.ensure_not_cancelled(job)

    with state.lock:
        _ensure_project_revision(start_revision)
        job_manager.ensure_not_cancelled(job)
        page_idx = _resolve_page_index(page_id)
        page = state.pages[page_idx]
        bubble = next((b for b in page.bubbles if b.id == bubble_id), None)
        if not bubble:
            raise RuntimeError("Bubble not found")
        bubble.translated = tb_block.translation
        invalidate_page_caches(page)
        state.touch()
        return {"translated": bubble.translated}


def _inpaint_single_bubble_job(job: dict, page_id: str, bubble_id: int):
    """Inpaint a single bubble."""
    with state.lock:
        page_idx = _resolve_page_index(page_id)
        page = state.pages[page_idx]
        ensure_page_image(page)
        bubble = next((b for b in page.bubbles if b.id == bubble_id), None)
        if not bubble:
            raise RuntimeError(f"Bubble {bubble_id} not found")
        start_revision = state.revision
        if page.inpainted_image is not None:
            image = page.inpainted_image.copy()
        else:
            image = page.cv_image.copy()
        bubble_snapshot = bubble.without_item()

    snapshots = [bubble_snapshot]
    boxes = inpaint_boxes(snapshots)
    bubble_boxes = bubble_clip_boxes(snapshots)

    job_manager.ensure_not_cancelled(job)
    job_manager.update(job, progress=30, message="Cleaning single bubble")
    inpainted_image = inpainting_service.clean_background(image, boxes, bubble_boxes, protect_edges=True)
    job_manager.ensure_not_cancelled(job)
    preview_bytes = encode_preview_jpeg_bytes(inpainted_image)
    job_manager.ensure_not_cancelled(job)

    with state.lock:
        _ensure_project_revision(start_revision)
        job_manager.ensure_not_cancelled(job)
        page_idx = _resolve_page_index(page_id)
        page = state.pages[page_idx]
        page.inpainted_image = inpainted_image
        invalidate_page_caches(page, thumbnails=True, layouts=False, responses=True)
        page._preview_inpainted_bytes = preview_bytes
        state.touch()
        return {"status": "ok"}


def _inpaint_job(job: dict, page_id: str):
    with state.lock:
        page_idx = _resolve_page_index(page_id)
        page = state.pages[page_idx]
        ensure_page_image(page)
        start_revision = state.revision
        image = page.cv_image.copy()
        bubbles_snapshot = [bubble.without_item() for bubble in page.bubbles]
        boxes = inpaint_boxes(bubbles_snapshot)
        bubble_boxes = bubble_clip_boxes(bubbles_snapshot)

    job_manager.ensure_not_cancelled(job)
    job_manager.update(job, progress=30, message="Cleaning text backgrounds")
    inpainted_image = inpainting_service.clean_background(image, boxes, bubble_boxes, protect_edges=True)
    job_manager.ensure_not_cancelled(job)
    preview_bytes = encode_preview_jpeg_bytes(inpainted_image)
    job_manager.ensure_not_cancelled(job)

    with state.lock:
        _ensure_project_revision(start_revision)
        job_manager.ensure_not_cancelled(job)
        page_idx = _resolve_page_index(page_id)
        page = state.pages[page_idx]
        page.inpainted_image = inpainted_image
        invalidate_page_caches(page, thumbnails=True, layouts=False, responses=True)
        page._preview_inpainted_bytes = preview_bytes
        state.touch()
        return {"status": "ok"}


@lru_cache(maxsize=64)
def resolve_font_path(font_family: str | None) -> str | None:
    """Resolve font path using the 6-level fallback chain.

    Delegates to FontResolverService for centralized font resolution.
    """
    from services.font_resolver_service import resolver as font_resolver

    resolved, chain = font_resolver.resolve(
        text="",
        requested_family=font_family,
        target_lang="Korean",
    )
    return resolved.path

@router.post("/api/pages/{page_id}/export")
def export_page(page_id: str, save_path: Optional[str] = Form(None), use_dialog: bool = Form(False)):
    with state.lock:
        source = _resolve_page(page_id)
        ensure_page_image(source)

        if source.inpainted_image is None:
            raise HTTPException(status_code=409, detail="Page must be cleaned before export")

        page = MangaPage(
            file_path=source.file_path,
            cv_image=source.cv_image.copy(),
            inpainted_image=source.inpainted_image.copy(),
            bubbles=[bubble.without_item() for bubble in source.bubbles],
            bubble_counter=source.bubble_counter,
        )

    font_path = resolve_font_path("Pretendard Variable")

    pil_image = export_service.render_page(
        page,
        font_path=font_path,
        font_family="Pretendard Variable",
        font_resolver=resolve_font_path
    )
    
    if pil_image is None:
        raise HTTPException(status_code=500, detail="Failed to render page image")
        
    if save_path:
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        pil_image.save(save_path)
        return {"status": "ok", "saved_path": save_path}
    else:
        buffer = io.BytesIO()
        pil_image.save(buffer, format="PNG")
        buffer.seek(0)
        return StreamingResponse(buffer, media_type="image/png")
