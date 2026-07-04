from typing import List

import numpy as np
from fastapi import HTTPException
from pydantic import BaseModel
from PySide6.QtCore import QRectF

from app.models import TextBubble
from domain.project_state import state
from modules.config import config
from modules.utils.textblock import TextBlock
from services.job_service import job_manager
from services.page_image_loader import ensure_page_image, invalidate_page_caches, load_cv_image
from services.review_state_service import derive_bubble_status, refresh_bubble_status, refresh_page_status
from services.service_registry import detection_service, render_service, translation_service
from app.version import APP_NAME

import logging

logger = logging.getLogger(APP_NAME)


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


def _rect_response(rect: QRectF | None) -> dict | None:
    if rect is None:
        return None
    return {
        "x": rect.x(),
        "y": rect.y(),
        "width": rect.width(),
        "height": rect.height(),
    }


def _get_page_by_id(page_id: str):
    for page in state.pages:
        if page.page_id == page_id:
            return page
    raise HTTPException(status_code=404, detail="Page not found")


def _get_page_index_by_id(page_id: str) -> int:
    for idx, page in enumerate(state.pages):
        if page.page_id == page_id:
            return idx
    raise HTTPException(status_code=404, detail="Page not found")


def _resolve_page(page_id: str):
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
    layout_box = bubble.layout_box
    return (
        bubble.id,
        round(box.x(), 2),
        round(box.y(), 2),
        round(box.width(), 2),
        round(box.height(), 2),
        tuple(round(v, 2) for v in bubble.source_xyxy()) if text_box is not None else None,
        (
            round(layout_box.x(), 2),
            round(layout_box.y(), 2),
            round(layout_box.width(), 2),
            round(layout_box.height(), 2),
        ) if layout_box is not None else None,
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
    computed_font_family = layout.font.family() if hasattr(layout.font, "family") else ""
    return {
        "font_size": bubble.font_size if bubble.font_size > 0 else int(layout.font.pointSizeF()),
        "font_family": computed_font_family,
        "lines": [
            {
                "text": line.text,
                "x": line.x,
                "y": line.y,
                "width": line.width,
                "height": line.height,
            }
            for line in layout.line_layouts
        ],
    }


def get_bubbles_response(page_id: str):
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
    for bubble in bubbles_snapshot:
        cached_layout = cached_layouts.get(bubble.id)
        if cached_layout is None:
            cached_layout = _compute_bubble_layout(bubble, source_img)
            computed_layouts[_layout_cache_key(bubble)] = cached_layout

        bubbles_list.append({
            "id": bubble.id,
            "x": bubble.box.x(),
            "y": bubble.box.y(),
            "width": bubble.box.width(),
            "height": bubble.box.height(),
            "text_box": _rect_response(bubble.text_box),
            "layout_box": _rect_response(bubble.layout_box),
            "text": bubble.text,
            "translated": bubble.translated,
            "font_family": bubble.font_family,
            "font_size": bubble.font_size,
            "computed_font_family": cached_layout.get("font_family", ""),
            "computed_font_size": cached_layout["font_size"],
            "bold": bubble.bold,
            "italic": bubble.italic,
            "color": bubble.color,
            "alignment": bubble.alignment,
            "text_class": bubble.text_class,
            "status": derive_bubble_status(bubble),
            "problems": list(bubble.problems),
            "edited": bubble.edited,
            "lines": cached_layout["lines"],
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


def update_bubbles_response(page_id: str, bubbles: List[BubbleUpdateSchema]):
    with state.lock:
        page = _resolve_page(page_id)

        updated_bubbles = []
        for b_schema in bubbles:
            existing = next((eb for eb in page.bubbles if eb.id == b_schema.id), None)
            text_box = existing.text_box if existing else None
            layout_box = existing.layout_box if existing else None
            text_class = existing.text_class if existing else "text_bubble"
            edited = bool(existing.edited) if existing else True
            problems = list(existing.problems) if existing else []
            status = existing.status if existing else "needs_review"
            if existing is not None:
                edited = edited or any((
                    existing.box.x() != b_schema.x,
                    existing.box.y() != b_schema.y,
                    existing.box.width() != b_schema.width,
                    existing.box.height() != b_schema.height,
                    existing.text != b_schema.text,
                    existing.translated != b_schema.translated,
                    existing.font_family != b_schema.font_family,
                    existing.font_size != b_schema.font_size,
                    existing.bold != b_schema.bold,
                    existing.italic != b_schema.italic,
                    existing.color != b_schema.color,
                    existing.alignment != b_schema.alignment,
                ))

            bubble = TextBubble(
                id=b_schema.id,
                box=QRectF(b_schema.x, b_schema.y, b_schema.width, b_schema.height),
                text=b_schema.text,
                translated=b_schema.translated,
                text_box=text_box,
                layout_box=layout_box,
                text_class=text_class,
                font_family=b_schema.font_family,
                font_size=b_schema.font_size,
                bold=b_schema.bold,
                italic=b_schema.italic,
                color=b_schema.color,
                alignment=b_schema.alignment,
                status=status,
                problems=problems,
                edited=edited,
            )
            refresh_bubble_status(bubble)
            updated_bubbles.append(bubble)

        page.bubbles = updated_bubbles
        page.bubble_counter = max(page.bubble_counter, max((b.id for b in page.bubbles), default=0))
        refresh_page_status(page)
        invalidate_page_caches(page)
        state.touch()
        return {"status": "ok"}


def re_ocr_bubble_response(page_id: str, bubble_id: int):
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
        bubble.edited = True
        refresh_page_status(page)
        invalidate_page_caches(page)
        state.touch()
        return {"status": "ok", "text": bubble.text}


def start_translate_bubble(page_id: str, bubble_id: int):
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
        text=bubble_snapshot.text,
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
        refresh_page_status(page)
        invalidate_page_caches(page)
        state.touch()
        return {"translated": bubble.translated}
