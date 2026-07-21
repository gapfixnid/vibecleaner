from types import SimpleNamespace
from typing import List

import numpy as np
from fastapi import HTTPException
from pydantic import BaseModel
from ...core.models import Rect, TextBubble
from ...infrastructure.image.loading import ensure_page_image, invalidate_page_caches, load_cv_image
from ...infrastructure.job_messages import msg
from ...core.state.review import derive_bubble_status, refresh_bubble_status, refresh_page_status
from ...core.version import APP_NAME
from ...engines.rendering.renderer import font_pixel_size
from .page_crud import resolve_page, resolve_page_index

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


def _rect_response(rect: Rect | None) -> dict | None:
    if rect is None:
        return None
    return {
        "x": rect.x,
        "y": rect.y,
        "width": rect.width,
        "height": rect.height,
    }


def _layout_overflow_problems(bubble: TextBubble, layout: dict) -> list[str]:
    problems = list(bubble.problems)
    if layout.get("overflow") or layout.get("reached_min_font"):
        if not any("layout overflow" == problem.lower() for problem in problems):
            problems.append("layout overflow")
    return problems




def _ensure_project_revision(state, start_revision: int) -> None:
    if state.revision != start_revision:
        raise RuntimeError("Project changed while the operation was running. Please retry.")


def _layout_cache_key(bubble: TextBubble) -> tuple:
    box = bubble.box
    text_box = bubble.text_box
    layout_box = bubble.layout_box
    return (
        bubble.id,
        round(box.x, 2),
        round(box.y, 2),
        round(box.width, 2),
        round(box.height, 2),
        tuple(round(v, 2) for v in bubble.source_xyxy()) if text_box is not None else None,
        (
            round(layout_box.x, 2),
            round(layout_box.y, 2),
            round(layout_box.width, 2),
            round(layout_box.height, 2),
        ) if layout_box is not None else None,
        bubble.text,
        bubble.translated,
        bubble.font_family,
        bubble.font_size,
        bubble.bold,
        bubble.italic,
        bubble.color,
        bubble.alignment,
        bubble.writing_mode,
        bubble.text_direction,
        bubble.justification,
        tuple(sorted(bubble.layout_padding.items())),
        tuple(sorted(bubble.layout_margin.items())),
        round(bubble.layout_confidence, 3),
        bubble.layout_reasoning,
    )


def _compute_bubble_layout(bubble: TextBubble, image, render_service) -> dict:
    layout = render_service.get_layout_for_bubble(
        bubble.translated or bubble.text or "",
        bubble,
        image=image,
        font_family=bubble.font_family or None,
    )
    computed_font_family = layout.font.family() if hasattr(layout.font, "family") else ""
    return {
        "font_size": bubble.font_size if bubble.font_size > 0 else font_pixel_size(layout.font),
        "font_family": computed_font_family,
        "overflow": bool(getattr(layout, "is_overflow", False)),
        "reached_min_font": bool(getattr(layout, "reached_min_font", False)),
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


def get_bubbles_response(state, page_id: str, render_service):
    with state.lock:
        page = resolve_page(state, page_id)
        loaded = getattr(page, "_loaded", True) and page.cv_image is not None and page.cv_image.size > 0
        source_img = page.cv_image if loaded else None
        load_path = page.file_path
        bubbles_snapshot = [bubble.clone() for bubble in page.bubbles]
        layout_cache = getattr(page, "_bubble_layout_cache", None)
        if layout_cache is None:
            layout_cache = {}
            page._bubble_layout_cache = layout_cache
        cached_layouts = {
            bubble.id: layout_cache.get(_layout_cache_key(bubble))
            for bubble in bubbles_snapshot
        }

    # A newly imported page has no bubbles to lay out. Avoid decoding and
    # retaining the full source image merely to return an empty response.
    if not bubbles_snapshot:
        return {"bubbles": []}

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
            cached_layout = _compute_bubble_layout(bubble, source_img, render_service)
            computed_layouts[_layout_cache_key(bubble)] = cached_layout

        problems = _layout_overflow_problems(bubble, cached_layout)
        status = derive_bubble_status(
            TextBubble(
                id=bubble.id,
                box=bubble.box,
                text=bubble.text,
                translated=bubble.translated,
                problems=problems,
                edited=bubble.edited,
                status=bubble.status,
            )
        )

        bubbles_list.append({
            "id": bubble.id,
            "x": bubble.box.x,
            "y": bubble.box.y,
            "width": bubble.box.width,
            "height": bubble.box.height,
            "text_box": _rect_response(bubble.text_box),
            "layout_box": _rect_response(bubble.layout_box),
            "text": bubble.text,
            "translated": bubble.translated,
            "font_family": bubble.font_family,
            "font_size": bubble.font_size,
            "computed_font_family": cached_layout.get("font_family", ""),
            "computed_font_size": cached_layout["font_size"],
            "writing_mode": bubble.writing_mode,
            "text_direction": bubble.text_direction,
            "justification": bubble.justification,
            "layout_padding": dict(bubble.layout_padding),
            "layout_margin": dict(bubble.layout_margin),
            "layout_confidence": bubble.layout_confidence,
            "detection_confidence": bubble.detection_confidence,
            "layout_reasoning": bubble.layout_reasoning,
            "layout_overflow": bool(cached_layout.get("overflow") or cached_layout.get("reached_min_font")),
            "bold": bubble.bold,
            "italic": bubble.italic,
            "color": bubble.color,
            "alignment": bubble.alignment,
            "text_class": bubble.text_class,
            "status": status,
            "problems": problems,
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


def update_bubbles_response(state, page_id: str, bubbles: List[BubbleUpdateSchema]):
    with state.lock:
        page = resolve_page(state, page_id)

        updated_bubbles = []
        for b_schema in bubbles:
            existing = next((eb for eb in page.bubbles if eb.id == b_schema.id), None)
            text_box = existing.text_box if existing else None
            layout_box = existing.layout_box if existing else None
            text_class = existing.text_class if existing else "text_bubble"
            writing_mode = existing.writing_mode if existing else "horizontal"
            text_direction = existing.text_direction if existing else "ltr"
            justification = existing.justification if existing else "none"
            layout_padding = dict(existing.layout_padding) if existing else {}
            layout_margin = dict(existing.layout_margin) if existing else {}
            layout_confidence = existing.layout_confidence if existing else 0.0
            detection_confidence = existing.detection_confidence if existing else 0.0
            layout_reasoning = existing.layout_reasoning if existing else ""
            edited = bool(existing.edited) if existing else True
            problems = list(existing.problems) if existing else []
            status = existing.status if existing else "needs_review"
            if existing is not None:
                edited = edited or any((
                    existing.box.x != b_schema.x,
                    existing.box.y != b_schema.y,
                    existing.box.width != b_schema.width,
                    existing.box.height != b_schema.height,
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
                box=Rect(b_schema.x, b_schema.y, b_schema.width, b_schema.height),
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
                writing_mode=writing_mode,
                text_direction=text_direction,
                justification=justification,
                layout_padding=layout_padding,
                layout_margin=layout_margin,
                layout_confidence=layout_confidence,
                detection_confidence=detection_confidence,
                layout_reasoning=layout_reasoning,
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


def re_ocr_bubble_response(state, page_id: str, bubble_id: int, detection_service, config):
    with state.lock:
        page = resolve_page(state, page_id)
        ensure_page_image(page)

        bubble = next((b for b in page.bubbles if b.id == bubble_id), None)
        if not bubble:
            raise HTTPException(status_code=404, detail="Bubble not found")
        image = page.cv_image.copy()
        box = bubble.box

    recognized_text = ""
    try:
        recognized_text = detection_service.recognize_region(
            image,
            [int(v) for v in box.to_xyxy()],
            lang=config.source_language,
        )
    except Exception as e:
        logger.warning("Failed to re-OCR bubble %s: %s", bubble_id, e)

    with state.lock:
        page = resolve_page(state, page_id)
        bubble = next((b for b in page.bubbles if b.id == bubble_id), None)
        if not bubble:
            raise HTTPException(status_code=404, detail="Bubble not found")
        bubble.text = recognized_text
        bubble.edited = True
        refresh_page_status(page)
        invalidate_page_caches(page)
        state.touch()
        return {"status": "ok", "text": bubble.text}


def start_translate_bubble(state, page_id: str, bubble_id: int, translation_service, config, job_manager):
    with state.lock:
        page = resolve_page(state, page_id)
        page_idx = resolve_page_index(state, page_id)
        if not any(b.id == bubble_id for b in page.bubbles):
            raise HTTPException(status_code=404, detail="Bubble not found")

    return job_manager.start(
        "translate-bubble",
        page_idx,
        f"translate-bubble:{page_id}:{bubble_id}",
        lambda job: _translate_single_bubble_job(
            state, job, page_id, bubble_id, translation_service, config, job_manager
        ),
    )


def _translate_single_bubble_job(state, job: dict, page_id: str, bubble_id: int, translation_service, config, job_manager):
    with state.lock:
        page_idx = resolve_page_index(state, page_id)
        page = state.pages[page_idx]
        ensure_page_image(page)
        bubble = next((b for b in page.bubbles if b.id == bubble_id), None)
        if not bubble:
            raise RuntimeError("Bubble not found")
        start_revision = state.revision
        image = page.cv_image.copy()
        bubble_snapshot = bubble.clone()

    job_manager.ensure_not_cancelled(job)
    job_manager.update(job, progress=30, message=msg("bubble.translate", config.ui_language))
    tb_block = SimpleNamespace(
        text_bbox=np.array(bubble_snapshot.source_xyxy()).astype(np.int32),
        text=bubble_snapshot.text,
        translation="",
    )
    translation_service.translate_blocks([tb_block], config.source_language, config.target_language, image)
    job_manager.ensure_not_cancelled(job)

    with state.lock:
        _ensure_project_revision(state, start_revision)
        job_manager.ensure_not_cancelled(job)
        page_idx = resolve_page_index(state, page_id)
        page = state.pages[page_idx]
        bubble = next((b for b in page.bubbles if b.id == bubble_id), None)
        if not bubble:
            raise RuntimeError("Bubble not found")
        bubble.translated = tb_block.translation
        refresh_page_status(page)
        invalidate_page_caches(page)
        state.touch()
        return {"translated": bubble.translated}
