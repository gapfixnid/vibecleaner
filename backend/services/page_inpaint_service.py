from fastapi import HTTPException

from pipeline.page_analysis import bubble_clip_boxes, inpaint_boxes
from services.image_encoding_service import encode_preview_jpeg_bytes
from services.job_service import job_manager
from services.page_crud_service import resolve_page, resolve_page_index
from services.page_image_loader import ensure_page_image, invalidate_page_caches
from services.review_state_service import refresh_page_status


def _ensure_project_revision(state, start_revision: int) -> None:
    if state.revision != start_revision:
        raise RuntimeError("Project changed while the operation was running. Please retry.")


def start_inpaint_bubble(state, page_id: str, bubble_id: int, inpainting_service):
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
        lambda job: _inpaint_single_bubble_job(state, job, page_id, bubble_id, inpainting_service),
    )


def start_inpaint_page(state, page_id: str, inpainting_service):
    with state.lock:
        page_idx = resolve_page_index(state, page_id)
    return job_manager.start("inpaint", page_idx, f"inpaint:{page_id}", lambda job: _inpaint_job(state, job, page_id, inpainting_service))


def _inpaint_single_bubble_job(state, job: dict, page_id: str, bubble_id: int, inpainting_service):
    with state.lock:
        page_idx = resolve_page_index(state, page_id)
        page = state.pages[page_idx]
        ensure_page_image(page)
        bubble = next((b for b in page.bubbles if b.id == bubble_id), None)
        if not bubble:
            raise RuntimeError(f"Bubble {bubble_id} not found")
        start_revision = state.revision
        image = page.inpainted_image.copy() if page.inpainted_image is not None else page.cv_image.copy()
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
        _ensure_project_revision(state, start_revision)
        job_manager.ensure_not_cancelled(job)
        page_idx = resolve_page_index(state, page_id)
        page = state.pages[page_idx]
        page.inpainted_image = inpainted_image
        refresh_page_status(page)
        invalidate_page_caches(page, thumbnails=True, layouts=False, responses=True)
        page._preview_inpainted_bytes = preview_bytes
        state.touch()
        return {"status": "ok"}


def _inpaint_job(state, job: dict, page_id: str, inpainting_service):
    with state.lock:
        page_idx = resolve_page_index(state, page_id)
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
        _ensure_project_revision(state, start_revision)
        job_manager.ensure_not_cancelled(job)
        page_idx = resolve_page_index(state, page_id)
        page = state.pages[page_idx]
        page.inpainted_image = inpainted_image
        refresh_page_status(page)
        invalidate_page_caches(page, thumbnails=True, layouts=False, responses=True)
        page._preview_inpainted_bytes = preview_bytes
        state.touch()
        return {"status": "ok"}
