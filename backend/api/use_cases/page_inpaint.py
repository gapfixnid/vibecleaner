from fastapi import HTTPException

from ...pipeline.page_analysis import (
    bubble_clip_boxes,
    bubble_source_polygons,
    inpaint_boxes,
    recover_missing_source_polygons,
)
from ...infrastructure.image.encoding import encode_preview_jpeg_bytes
from ...infrastructure.image.loading import ensure_page_image, invalidate_page_caches
from ...infrastructure.job_messages import msg
from ...core.state.review import refresh_page_status

from .page_crud import resolve_page, resolve_page_index


def _ensure_page_guard(state, page_id: str, page_object, project_generation: int, visual_revision: int):
    if state.project_generation != project_generation:
        raise RuntimeError("Project changed while the operation was running. Please retry.")
    page = state.pages[resolve_page_index(state, page_id)]
    if page is not page_object:
        raise RuntimeError("Page was replaced while the operation was running. Please retry.")
    if page.visual_revision != visual_revision:
        raise RuntimeError("Page changed while the operation was running. Please retry.")
    return page


def _commit_inpaint_visual_change(state, page, inpainted_image, preview_bytes) -> None:
    page.inpainted_image = inpainted_image
    page.image_visual_revision += 1
    page.visual_revision += 1
    page.text_layer_refs.clear()
    page.bubble_render_status.clear()
    refresh_page_status(page)
    invalidate_page_caches(page, thumbnails=True, layouts=False, responses=True)
    page._preview_inpainted_bytes = preview_bytes
    state.touch()


def start_inpaint_bubble(state, page_id: str, bubble_id: int, inpainting_service, job_manager, config=None):
    with state.lock:
        page = resolve_page(state, page_id)
        page_idx = resolve_page_index(state, page_id)
        ensure_page_image(page)
        bubble = next((b for b in page.bubbles if b.id == bubble_id), None)
        if not bubble:
            raise HTTPException(status_code=404, detail="Bubble not found")

    return job_manager.start(
        "inpaint-bubble",
        page_idx,
        f"inpaint-bubble:{page_id}:{bubble_id}",
        lambda job: _inpaint_single_bubble_job(state, job, page_id, bubble_id, inpainting_service, job_manager, config),
    )


def start_inpaint_page(state, page_id: str, inpainting_service, job_manager, config=None):
    with state.lock:
        page_idx = resolve_page_index(state, page_id)
    return job_manager.start(
        "inpaint",
        page_idx,
        f"inpaint:{page_id}",
        lambda job: _inpaint_job(state, job, page_id, inpainting_service, job_manager, config),
    )


def _inpaint_single_bubble_job(state, job: dict, page_id: str, bubble_id: int, inpainting_service, job_manager, config=None):
    ui_lang = config.ui_language if config else "en"
    with state.lock:
        page_idx = resolve_page_index(state, page_id)
        page = state.pages[page_idx]
        ensure_page_image(page)
        bubble = next((b for b in page.bubbles if b.id == bubble_id), None)
        if not bubble:
            raise RuntimeError(f"Bubble {bubble_id} not found")
        page_object = page
        project_generation = state.project_generation
        visual_revision = page.visual_revision
        image = page.inpainted_image.copy() if page.inpainted_image is not None else page.cv_image.copy()
        bubble_snapshot = bubble.clone()

    snapshots = [bubble_snapshot]
    recover_missing_source_polygons(
        image,
        snapshots,
        source_language=str(getattr(config, "source_language", "")),
    )
    boxes = inpaint_boxes(
        snapshots,
        use_textbox_only=bool(getattr(config, "inpaint_use_textbox_only", True)),
    )
    bubble_boxes = bubble_clip_boxes(snapshots)

    job_manager.ensure_not_cancelled(job)
    job_manager.update(job, progress=30, message=msg("inpaint.bubble", ui_lang))
    inpainted_image = inpainting_service.clean_background(
        image,
        boxes,
        bubble_boxes,
        source_polygons=bubble_source_polygons(snapshots),
        protect_edges=True,
    )
    job_manager.ensure_not_cancelled(job)
    preview_bytes = encode_preview_jpeg_bytes(inpainted_image)
    job_manager.ensure_not_cancelled(job)

    with state.lock:
        page = _ensure_page_guard(state, page_id, page_object, project_generation, visual_revision)
        job_manager.ensure_not_cancelled(job)
        current_bubble = next((item for item in page.bubbles if item.id == bubble_snapshot.id), None)
        if current_bubble is not None and bubble_snapshot.source_polygons:
            current_bubble.source_polygons = bubble_snapshot.source_polygons
            current_bubble.text_box = bubble_snapshot.text_box
        _commit_inpaint_visual_change(state, page, inpainted_image, preview_bytes)
        return {"status": "ok", "visual_revision": page.visual_revision}


def _inpaint_job(state, job: dict, page_id: str, inpainting_service, job_manager, config=None):
    ui_lang = config.ui_language if config else "en"
    with state.lock:
        page_idx = resolve_page_index(state, page_id)
        page = state.pages[page_idx]
        ensure_page_image(page)
        page_object = page
        project_generation = state.project_generation
        visual_revision = page.visual_revision
        image = page.cv_image.copy()
        bubbles_snapshot = [bubble.clone() for bubble in page.bubbles]
        recover_missing_source_polygons(
            image,
            bubbles_snapshot,
            source_language=str(getattr(config, "source_language", "")),
        )
        boxes = inpaint_boxes(
            bubbles_snapshot,
            use_textbox_only=bool(getattr(config, "inpaint_use_textbox_only", True)),
        )
        bubble_boxes = bubble_clip_boxes(bubbles_snapshot)

    job_manager.ensure_not_cancelled(job)
    job_manager.update(job, progress=30, message=msg("inpaint.page", ui_lang))
    inpainted_image = inpainting_service.clean_background(
        image,
        boxes,
        bubble_boxes,
        source_polygons=bubble_source_polygons(bubbles_snapshot),
        protect_edges=True,
    )
    job_manager.ensure_not_cancelled(job)
    preview_bytes = encode_preview_jpeg_bytes(inpainted_image)
    job_manager.ensure_not_cancelled(job)

    with state.lock:
        page = _ensure_page_guard(state, page_id, page_object, project_generation, visual_revision)
        job_manager.ensure_not_cancelled(job)
        recovered_by_id = {bubble.id: bubble for bubble in bubbles_snapshot if bubble.source_polygons}
        for current_bubble in page.bubbles:
            recovered = recovered_by_id.get(current_bubble.id)
            if recovered is not None:
                current_bubble.source_polygons = recovered.source_polygons
                current_bubble.text_box = recovered.text_box
        _commit_inpaint_visual_change(state, page, inpainted_image, preview_bytes)
        return {"status": "ok", "visual_revision": page.visual_revision}
