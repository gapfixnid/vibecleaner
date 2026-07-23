from types import SimpleNamespace
from typing import List

import numpy as np
from fastapi import HTTPException
from pydantic import BaseModel
from ...core.models import (
    BubbleProblemCode,
    Rect,
    TextBubble,
    reconcile_bubble_problems,
)
from ...infrastructure.image.loading import ensure_page_image, invalidate_page_caches, load_cv_image
from ...infrastructure.job_messages import msg
from ...core.state.review import derive_bubble_status, refresh_bubble_status, refresh_page_status
from ...core.version import APP_NAME
from ...engines.rendering.bubble_layout import (
    bubble_layout_cache_key as _layout_cache_key,
    compute_bubble_layout as _compute_bubble_layout,
)
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


class BubbleMutationRequest(BaseModel):
    expected_project_generation: int
    expected_visual_revision: int
    bubbles: List[BubbleUpdateSchema]


class VisualMutationPrecondition(BaseModel):
    expected_project_generation: int
    expected_visual_revision: int


def _rect_response(rect: Rect | None) -> dict | None:
    if rect is None:
        return None
    return {
        "x": rect.x,
        "y": rect.y,
        "width": rect.width,
        "height": rect.height,
    }


def _layout_overflow_problems(bubble: TextBubble, layout: dict) -> list:
    derived = {
        BubbleProblemCode(code)
        for code in bubble._derived_problem_codes
        if code in BubbleProblemCode._value2member_map_
    }
    if layout.get("overflow") or layout.get("reached_min_font"):
        derived.add(BubbleProblemCode.TEXT_OVERFLOW)
    return reconcile_bubble_problems(
        bubble.problems,
        derived=derived,
    )


def _problem_response(problems: list) -> list[dict]:
    return [problem.to_dict() for problem in problems]

def _text_layer_ref_response(ref: dict | None) -> dict | None:
    if not ref:
        return None
    return {
        "cache_key": ref["cache_key"],
        "pixel_digest": ref["pixel_digest"],
        "crop_x": ref["crop_x"],
        "crop_y": ref["crop_y"],
        "width": ref["width"],
        "height": ref["height"],
        "mime_type": "image/png",
    }


def get_bubbles_response(state, page_id: str, render_service, text_layer_service=None):
    with state.lock:
        page = resolve_page(state, page_id)
        page_object = page
        start_project_generation = state.project_generation
        start_content_revision = state.content_revision
        start_visual_revision = page.visual_revision
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
        existing_render_statuses = dict(page.bubble_render_status)
        existing_layer_refs = dict(page.text_layer_refs)

    # A newly imported page has no bubbles to lay out. Avoid decoding and
    # retaining the full source image merely to return an empty response.
    if not bubbles_snapshot:
        return {
            "page_id": page_id,
            "project_generation": start_project_generation,
            "content_revision": start_content_revision,
            "visual_revision": start_visual_revision,
            "text_layer_namespace": getattr(text_layer_service, "namespace", ""),
            "bubbles": [],
        }
    if source_img is None:
        source_img = load_cv_image(load_path)
        if source_img is None:
            logger.error("Failed to load page image for bubble layout: %s", load_path)
            raise HTTPException(status_code=500, detail="Failed to load page image")

    computed_layouts = {}
    computed_layers: dict[int, tuple[dict | None, dict]] = {}
    bubbles_list = []
    for bubble in bubbles_snapshot:
        cached_layout = cached_layouts.get(bubble.id)
        layer_ref = None
        render_status = {"status": "ready", "error_code": None}
        stroke_color = "#ffffff"
        stroke_width = max(1.0, float(bubble.font_size or 12) / 12.0)
        prior_status = existing_render_statuses.get(bubble.id)
        if prior_status and prior_status.get("status") == "fallback":
            render_status = dict(prior_status)
            layer_ref = existing_layer_refs.get(bubble.id)
        elif text_layer_service is not None and (bubble.translated or "").strip():
            try:
                tile = text_layer_service.create_tile(
                    page_id,
                    bubble,
                    source_img,
                    image_revision=getattr(page_object, "image_visual_revision", 0),
                )
                cached_layout = tile.layout
                layer_ref = {
                    "layout_fingerprint": tile.layout_fingerprint,
                    "render_fingerprint": tile.render_fingerprint,
                    "cache_key": tile.cache_key,
                    "pixel_digest": tile.pixel_digest,
                    "crop_x": tile.crop_x,
                    "crop_y": tile.crop_y,
                    "width": tile.width,
                    "height": tile.height,
                }
                stroke_color = tile.stroke_color
                stroke_width = tile.stroke_width
            except Exception as exc:
                logger.warning("Text layer fallback for bubble %s: %s", bubble.id, exc)
                render_status = {"status": "fallback", "error_code": str(exc)}
        if cached_layout is None:
            cached_layout = _compute_bubble_layout(bubble, source_img, render_service)
            computed_layouts[_layout_cache_key(bubble)] = cached_layout
        computed_layers[bubble.id] = (layer_ref, render_status)

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
            "font_mode": cached_layout.get("font_mode", "fixed" if bubble.font_size > 0 else "auto"),
            "requested_font_size": cached_layout.get(
                "requested_font_size",
                bubble.font_size if bubble.font_size > 0 else None,
            ),
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
            "line_height_ratio": float(cached_layout.get("line_height_ratio", 1.0)),
            "layout_area_usage": float(cached_layout.get("area_usage", 0.0)),
            "layout_diagnostics": dict(
                cached_layout.get("diagnostics", {}) or {}
            ),
            "bold": bubble.bold,
            "italic": bubble.italic,
            "color": bubble.color,
            "alignment": bubble.alignment,
            "text_class": bubble.text_class,
            "status": status,
            "problems": _problem_response(problems),
            "edited": bubble.edited,
            "lines": [
                {
                    **line,
                    "x": line.get("x", line.get("ink_left", line.get("origin_x", 0))),
                    "y": line.get("y", line.get("ink_top", line.get("baseline_y", 0))),
                    "width": line.get("width", line.get("ink_width", line.get("advance_width", 0))),
                    "height": line.get("height", line.get("ink_height", cached_layout.get("font_size", 12))),
                }
                for line in cached_layout["lines"]
            ],
            "text_layer": _text_layer_ref_response(layer_ref),
            "render_status": render_status,
            "stroke_color": stroke_color,
            "stroke_width": stroke_width,
        })

    with state.lock:
        if state.project_generation != start_project_generation:
            raise HTTPException(status_code=409, detail={"code": "PROJECT_REPLACED"})
        if not any(existing is page_object for existing in state.pages):
            raise HTTPException(status_code=409, detail={"code": "PAGE_REPLACED"})
        if page_object.visual_revision == start_visual_revision:
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
            for bubble_id, (layer_ref, render_status) in computed_layers.items():
                if layer_ref is None:
                    page_object.text_layer_refs.pop(bubble_id, None)
                else:
                    page_object.text_layer_refs[bubble_id] = layer_ref
                page_object.bubble_render_status[bubble_id] = render_status
        response_content_revision = state.content_revision

    return {
        "page_id": page_id,
        "project_generation": start_project_generation,
        "content_revision": response_content_revision,
        "visual_revision": start_visual_revision,
        "text_layer_namespace": getattr(text_layer_service, "namespace", ""),
        "bubbles": bubbles_list,
    }


def update_bubbles_response(
    state,
    page_id: str,
    request: BubbleMutationRequest,
    render_service,
    text_layer_service,
):
    with state.lock:
        page = resolve_page(state, page_id)
        if state.project_generation != request.expected_project_generation:
            raise HTTPException(status_code=409, detail={"code": "PROJECT_REPLACED"})
        if page.visual_revision != request.expected_visual_revision:
            raise HTTPException(status_code=409, detail={"code": "VISUAL_REVISION_CONFLICT"})
        snapshot_page = page
        ensure_page_image(page)
        source_img = page.cv_image.copy()
        old_by_id = {bubble.id: bubble for bubble in page.bubbles}

        updated_bubbles: list[TextBubble] = []
        for b_schema in request.bubbles:
            if (
                b_schema.id < 1
                or not all(np.isfinite(value) for value in (b_schema.x, b_schema.y, b_schema.width, b_schema.height))
                or b_schema.width <= 0
                or b_schema.height <= 0
                or b_schema.x < 0
                or b_schema.y < 0
                or b_schema.x + b_schema.width > source_img.shape[1]
                or b_schema.y + b_schema.height > source_img.shape[0]
            ):
                raise HTTPException(status_code=422, detail={"code": "INVALID_BUBBLE_GEOMETRY"})
            existing = old_by_id.get(b_schema.id)
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
        old_ids = set(old_by_id)
        new_ids = {bubble.id for bubble in updated_bubbles}
        deleted_ids = sorted(old_ids - new_ids)
        changed_ids = {
            bubble.id
            for bubble in updated_bubbles
            if bubble.id not in old_by_id or bubble.to_project_dict() != old_by_id[bubble.id].to_project_dict()
        }

    if not changed_ids and not deleted_ids:
        return {
            "status": "ok",
            "page_id": page_id,
            "project_generation": request.expected_project_generation,
            "content_revision": state.content_revision,
            "visual_revision": request.expected_visual_revision,
            "text_layer_namespace": text_layer_service.namespace,
            "changed_bubbles": [],
            "deleted_bubble_ids": [],
        }

    # Derived assets are prepared without holding the project lock. Failure is
    # recorded per bubble and never rolls back valid user content.
    prepared: dict[int, tuple[dict | None, dict]] = {}
    for bubble in updated_bubbles:
        if bubble.id not in changed_ids:
            continue
        if not (bubble.translated or "").strip():
            prepared[bubble.id] = (None, {"status": "ready", "error_code": None})
            continue
        try:
            tile = text_layer_service.create_tile(
                page_id,
                bubble,
                source_img,
                image_revision=snapshot_page.image_visual_revision,
            )
            prepared[bubble.id] = ({
                "layout_fingerprint": tile.layout_fingerprint,
                "render_fingerprint": tile.render_fingerprint,
                "cache_key": tile.cache_key,
                "pixel_digest": tile.pixel_digest,
                "crop_x": tile.crop_x,
                "crop_y": tile.crop_y,
                "width": tile.width,
                "height": tile.height,
            }, {"status": "ready", "error_code": None})
        except Exception as exc:
            logger.warning("Text layer mutation fallback for bubble %s: %s", bubble.id, exc)
            prepared[bubble.id] = (None, {"status": "fallback", "error_code": str(exc)})

    with state.lock:
        if state.project_generation != request.expected_project_generation:
            raise HTTPException(status_code=409, detail={"code": "PROJECT_REPLACED"})
        current_page = resolve_page(state, page_id)
        if current_page is not snapshot_page:
            raise HTTPException(status_code=409, detail={"code": "PAGE_REPLACED"})
        if current_page.visual_revision != request.expected_visual_revision:
            raise HTTPException(status_code=409, detail={"code": "VISUAL_REVISION_CONFLICT"})

        current_page.bubbles = updated_bubbles
        current_page.bubble_counter = max(current_page.bubble_counter, max((b.id for b in updated_bubbles), default=0))
        for bubble_id in deleted_ids:
            current_page.text_layer_refs.pop(bubble_id, None)
            current_page.bubble_render_status.pop(bubble_id, None)
        for bubble_id, (ref, status) in prepared.items():
            if ref is None:
                current_page.text_layer_refs.pop(bubble_id, None)
            else:
                current_page.text_layer_refs[bubble_id] = ref
            current_page.bubble_render_status[bubble_id] = status
        refresh_page_status(current_page)
        invalidate_page_caches(current_page)
        current_page.visual_revision += 1
        state.touch()
        visual_revision = current_page.visual_revision
        content_revision = state.content_revision
        project_generation = state.project_generation

    snapshot = get_bubbles_response(state, page_id, render_service, text_layer_service)
    changed = [bubble for bubble in snapshot["bubbles"] if bubble["id"] in changed_ids]
    return {
        "status": "ok",
        "page_id": page_id,
        "project_generation": project_generation,
        "content_revision": content_revision,
        "visual_revision": visual_revision,
        "text_layer_namespace": text_layer_service.namespace,
        "changed_bubbles": changed,
        "deleted_bubble_ids": deleted_ids,
    }


def re_ocr_bubble_response(
    state,
    page_id: str,
    bubble_id: int,
    precondition: VisualMutationPrecondition,
    detection_service,
    config,
    text_layer_service,
):
    with state.lock:
        page = resolve_page(state, page_id)
        if state.project_generation != precondition.expected_project_generation:
            raise HTTPException(status_code=409, detail={"code": "PROJECT_REPLACED"})
        if page.visual_revision != precondition.expected_visual_revision:
            raise HTTPException(status_code=409, detail={"code": "VISUAL_REVISION_CONFLICT"})
        ensure_page_image(page)
        bubble = next((b for b in page.bubbles if b.id == bubble_id), None)
        if not bubble:
            raise HTTPException(status_code=404, detail="Bubble not found")
        snapshot_page = page
        bubble_snapshot = bubble.clone()
        image = page.cv_image.copy()
        image_revision = page.image_visual_revision
        box = bubble.box

    recognized_text = ""
    try:
        recognized_text = detection_service.recognize_region(
            image,
            [int(v) for v in box.to_xyxy()],
            lang=config.source_language,
        )
    except Exception as exc:
        logger.warning("Failed to re-OCR bubble %s: %s", bubble_id, exc)

    proposed = bubble_snapshot.clone()
    proposed.text = recognized_text
    prepared_ref = None
    render_status = {"status": "ready", "error_code": None}
    if (proposed.translated or "").strip():
        try:
            tile = text_layer_service.create_tile(page_id, proposed, image, image_revision=image_revision)
            prepared_ref = {
                "layout_fingerprint": tile.layout_fingerprint,
                "render_fingerprint": tile.render_fingerprint,
                "cache_key": tile.cache_key,
                "pixel_digest": tile.pixel_digest,
                "crop_x": tile.crop_x,
                "crop_y": tile.crop_y,
                "width": tile.width,
                "height": tile.height,
            }
        except Exception as exc:
            render_status = {"status": "fallback", "error_code": str(exc)}

    with state.lock:
        page = resolve_page(state, page_id)
        if state.project_generation != precondition.expected_project_generation:
            raise HTTPException(status_code=409, detail={"code": "PROJECT_REPLACED"})
        if page is not snapshot_page:
            raise HTTPException(status_code=409, detail={"code": "PAGE_REPLACED"})
        if page.visual_revision != precondition.expected_visual_revision:
            raise HTTPException(status_code=409, detail={"code": "VISUAL_REVISION_CONFLICT"})
        bubble = next((b for b in page.bubbles if b.id == bubble_id), None)
        if not bubble:
            raise HTTPException(status_code=404, detail="Bubble not found")
        bubble.text = recognized_text
        bubble.edited = True
        if prepared_ref is None:
            page.text_layer_refs.pop(bubble_id, None)
        else:
            page.text_layer_refs[bubble_id] = prepared_ref
        page.bubble_render_status[bubble_id] = render_status
        refresh_page_status(page)
        invalidate_page_caches(page)
        page.visual_revision += 1
        state.touch()
        return {
            "status": "ok",
            "text": bubble.text,
            "project_generation": state.project_generation,
            "content_revision": state.content_revision,
            "visual_revision": page.visual_revision,
        }


def start_translate_bubble(
    state,
    page_id: str,
    bubble_id: int,
    precondition: VisualMutationPrecondition,
    translation_service,
    config,
    job_manager,
    text_layer_service,
):
    with state.lock:
        page = resolve_page(state, page_id)
        page_idx = resolve_page_index(state, page_id)
        if state.project_generation != precondition.expected_project_generation:
            raise HTTPException(status_code=409, detail={"code": "PROJECT_REPLACED"})
        if page.visual_revision != precondition.expected_visual_revision:
            raise HTTPException(status_code=409, detail={"code": "VISUAL_REVISION_CONFLICT"})
        if not any(b.id == bubble_id for b in page.bubbles):
            raise HTTPException(status_code=404, detail="Bubble not found")
        snapshot_page = page

    return job_manager.start(
        "translate-bubble",
        page_idx,
        f"translate-bubble:{page_id}:{bubble_id}",
        lambda job: _translate_single_bubble_job(
            state, job, page_id, bubble_id, translation_service, config, job_manager,
            text_layer_service, precondition, snapshot_page,
        ),
    )


def _translate_single_bubble_job(
    state, job: dict, page_id: str, bubble_id: int, translation_service, config,
    job_manager, text_layer_service, precondition, snapshot_page,
):
    with state.lock:
        page_idx = resolve_page_index(state, page_id)
        page = state.pages[page_idx]
        ensure_page_image(page)
        bubble = next((b for b in page.bubbles if b.id == bubble_id), None)
        if not bubble:
            raise RuntimeError("Bubble not found")
        image = page.cv_image.copy()
        image_revision = page.image_visual_revision
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
    proposed = bubble_snapshot.clone()
    proposed.translated = tb_block.translation
    prepared_ref = None
    render_status = {"status": "ready", "error_code": None}
    if (proposed.translated or "").strip():
        try:
            tile = text_layer_service.create_tile(page_id, proposed, image, image_revision=image_revision)
            prepared_ref = {
                "layout_fingerprint": tile.layout_fingerprint,
                "render_fingerprint": tile.render_fingerprint,
                "cache_key": tile.cache_key,
                "pixel_digest": tile.pixel_digest,
                "crop_x": tile.crop_x,
                "crop_y": tile.crop_y,
                "width": tile.width,
                "height": tile.height,
            }
        except Exception as exc:
            render_status = {"status": "fallback", "error_code": str(exc)}

    with state.lock:
        if state.project_generation != precondition.expected_project_generation:
            raise RuntimeError("Project was replaced while translation was running")
        job_manager.ensure_not_cancelled(job)
        page_idx = resolve_page_index(state, page_id)
        page = state.pages[page_idx]
        if page is not snapshot_page:
            raise RuntimeError("Page was replaced while translation was running")
        if page.visual_revision != precondition.expected_visual_revision:
            raise RuntimeError("Page changed while translation was running")
        bubble = next((b for b in page.bubbles if b.id == bubble_id), None)
        if not bubble:
            raise RuntimeError("Bubble not found")
        bubble.translated = tb_block.translation
        if prepared_ref is None:
            page.text_layer_refs.pop(bubble_id, None)
        else:
            page.text_layer_refs[bubble_id] = prepared_ref
        page.bubble_render_status[bubble_id] = render_status
        refresh_page_status(page)
        invalidate_page_caches(page)
        page.visual_revision += 1
        state.touch()
        return {
            "translated": bubble.translated,
            "project_generation": state.project_generation,
            "content_revision": state.content_revision,
            "visual_revision": page.visual_revision,
        }
