from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Form
from pydantic import BaseModel

from api.dependencies import get_container
from core.container import AppContainer
from services.bubble_service import (
    BubbleUpdateSchema,
    get_bubbles_response,
    re_ocr_bubble_response,
    start_translate_bubble,
    update_bubbles_response,
)
from services.page_image_service import get_page_image_response
from services.page_crud_service import (
    delete_page_batch_response,
    delete_page_response,
    duplicate_page_batch_response,
    duplicate_page_response,
    get_pages_response,
    rename_page_response,
    reorder_pages_response,
    resolve_indices_from_request as _resolve_indices_from_request,
    resolve_page_index as _resolve_page_index,
    select_page_response,
)
from services.page_export_service import export_page_response
from services.page_inpaint_service import start_inpaint_bubble, start_inpaint_page
from pipeline.page_translation import run_page_translation
router = APIRouter()


class TranslateBatchRequest(BaseModel):
    page_indices: Optional[List[int]] = None
    page_ids: Optional[List[str]] = None

@router.get("/api/pages")
def get_pages(container: AppContainer = Depends(get_container)):
    return get_pages_response(container.legacy_state)

@router.post("/api/pages/select")
def select_page(
    index: Optional[int] = Form(None),
    page_id: Optional[str] = Form(None),
    container: AppContainer = Depends(get_container),
):
    return select_page_response(container.legacy_state, index=index, page_id=page_id)

@router.post("/api/pages/{page_id}/rename")
def rename_page(page_id: str, name: str = Form(...), container: AppContainer = Depends(get_container)):
    return rename_page_response(container.legacy_state, page_id, name)


@router.post("/api/pages/duplicate")
def duplicate_page(
    index: Optional[int] = Form(None),
    page_id: Optional[str] = Form(None),
    container: AppContainer = Depends(get_container),
):
    return duplicate_page_response(container.legacy_state, index=index, page_id=page_id)


@router.post("/api/pages/duplicate-batch")
def duplicate_page_batch(req: TranslateBatchRequest, container: AppContainer = Depends(get_container)):
    return duplicate_page_batch_response(container.legacy_state, req)


@router.post("/api/pages/delete")
def delete_page(
    index: Optional[int] = Form(None),
    page_id: Optional[str] = Form(None),
    container: AppContainer = Depends(get_container),
):
    return delete_page_response(container.legacy_state, index=index, page_id=page_id)


@router.post("/api/pages/delete-batch")
def delete_page_batch(req: TranslateBatchRequest, container: AppContainer = Depends(get_container)):
    return delete_page_batch_response(container.legacy_state, req)

@router.post("/api/pages/reorder")
def reorder_pages(
    from_index: int = Form(...),
    to_index: int = Form(...),
    container: AppContainer = Depends(get_container),
):
    return reorder_pages_response(container.legacy_state, from_index, to_index)

@router.get("/api/pages/{page_id}/image")
def get_page_image(
    page_id: str,
    type: str = "original",
    thumbnail: bool = False,
    preview: bool = False,
    container: AppContainer = Depends(get_container),
):
    return get_page_image_response(container.legacy_state, page_id, image_type=type, thumbnail=thumbnail, preview=preview)

@router.get("/api/pages/{page_id}/bubbles")
def get_bubbles(page_id: str, container: AppContainer = Depends(get_container)):
    return get_bubbles_response(container.legacy_state, page_id, container.render_service)

@router.post("/api/pages/{page_id}/bubbles")
def update_bubbles(
    page_id: str,
    bubbles: List[BubbleUpdateSchema],
    container: AppContainer = Depends(get_container),
):
    return update_bubbles_response(container.legacy_state, page_id, bubbles)

@router.post("/api/pages/{page_id}/bubbles/{bubble_id}/ocr")
def re_ocr_bubble(page_id: str, bubble_id: int, container: AppContainer = Depends(get_container)):
    return re_ocr_bubble_response(container.legacy_state, page_id, bubble_id, container.detection_service, container.config)

@router.post("/api/pages/{page_id}/bubbles/{bubble_id}/translate")
def translate_single_bubble(page_id: str, bubble_id: int, container: AppContainer = Depends(get_container)):
    return start_translate_bubble(container.legacy_state, page_id, bubble_id, container.translation_service, container.config)

@router.post("/api/pages/{page_id}/bubbles/{bubble_id}/inpaint")
def inpaint_single_bubble(page_id: str, bubble_id: int, container: AppContainer = Depends(get_container)):
    return start_inpaint_bubble(container.legacy_state, page_id, bubble_id, container.inpainting_service)

@router.post("/api/pages/{page_id}/inpaint")
def run_inpaint(page_id: str, container: AppContainer = Depends(get_container)):
    return start_inpaint_page(container.legacy_state, page_id, container.inpainting_service)

@router.post("/api/pages/{page_id}/translate-all")
def run_translate_all(page_id: str, container: AppContainer = Depends(get_container)):
    with container.legacy_state.lock:
        page_idx = _resolve_page_index(container.legacy_state, page_id)
    return container.job_manager.start(
        "page-translation",
        page_idx,
        f"page-translation:{page_id}",
        lambda job: run_page_translation(
            job=job,
            page_id=page_id,
            state=container.legacy_state,
            config=container.config,
            job_manager=container.job_manager,
            runner=container.pipeline_runner,
            planner=container.pipeline_planner,
            show_progress=True,
        ),
    )

@router.post("/api/pages/translate-batch")
def run_translate_batch(req: TranslateBatchRequest, container: AppContainer = Depends(get_container)):
    """Translate multiple pages as a single batch job."""
    with container.legacy_state.lock:
        valid_indices = _resolve_indices_from_request(container.legacy_state, req)
        if not valid_indices:
            raise HTTPException(status_code=400, detail="No valid pages to translate")
        page_ids = [container.legacy_state.pages[idx].page_id for idx in valid_indices]
        first_idx = valid_indices[0]

    key = f"page-translation-batch:{','.join(page_ids)}"
    return container.job_manager.start(
        "page-translation-batch",
        first_idx,
        key,
        lambda job: _run_translate_batch_pages(job, page_ids, container),
    )


def _run_translate_batch_pages(job: dict, page_ids: List[str], container: AppContainer) -> dict:
    total = len(page_ids)
    completed = 0
    completed_page_indices = []

    for page_id in page_ids:
        page_idx = None
        try:
            with container.legacy_state.lock:
                page_idx = _resolve_page_index(container.legacy_state, page_id)
            container.job_manager.update(
                job,
                progress=int((completed / total) * 100),
                message=f"Translating page {completed + 1}/{total}...",
            )
            job["result"] = {"completed_pages": list(completed_page_indices), "total_pages": total}
            run_page_translation(
                job=job,
                page_id=page_id,
                state=container.legacy_state,
                config=container.config,
                job_manager=container.job_manager,
                runner=container.pipeline_runner,
                planner=container.pipeline_planner,
                show_progress=False,
            )
        except HTTPException:
            pass
        except RuntimeError as exc:
            if "cancelled" in str(exc).lower():
                raise
            completed += 1
            continue

        completed += 1
        if page_idx is not None:
            completed_page_indices.append(page_idx)
            container.job_manager.ensure_not_cancelled(job)

    container.job_manager.update(job, progress=100, message="Batch translation complete")
    return {"translated_pages": completed, "total_pages": total, "completed_pages": completed_page_indices}


@router.post("/api/pages/{page_id}/export")
def export_page(
    page_id: str,
    save_path: Optional[str] = Form(None),
    use_dialog: bool = Form(False),
    container: AppContainer = Depends(get_container),
):
    return export_page_response(container.legacy_state, page_id, container.export_service, save_path=save_path)
