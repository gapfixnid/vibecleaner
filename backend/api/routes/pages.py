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
router = APIRouter()


class TranslateBatchRequest(BaseModel):
    page_indices: Optional[List[int]] = None
    page_ids: Optional[List[str]] = None

@router.get("/api/pages")
def get_pages():
    return get_pages_response()

@router.post("/api/pages/select")
def select_page(index: Optional[int] = Form(None), page_id: Optional[str] = Form(None)):
    return select_page_response(index=index, page_id=page_id)

@router.post("/api/pages/{page_id}/rename")
def rename_page(page_id: str, name: str = Form(...)):
    return rename_page_response(page_id, name)


@router.post("/api/pages/duplicate")
def duplicate_page(index: Optional[int] = Form(None), page_id: Optional[str] = Form(None)):
    return duplicate_page_response(index=index, page_id=page_id)


@router.post("/api/pages/duplicate-batch")
def duplicate_page_batch(req: TranslateBatchRequest):
    return duplicate_page_batch_response(req)


@router.post("/api/pages/delete")
def delete_page(index: Optional[int] = Form(None), page_id: Optional[str] = Form(None)):
    return delete_page_response(index=index, page_id=page_id)


@router.post("/api/pages/delete-batch")
def delete_page_batch(req: TranslateBatchRequest):
    return delete_page_batch_response(req)

@router.post("/api/pages/reorder")
def reorder_pages(from_index: int = Form(...), to_index: int = Form(...)):
    return reorder_pages_response(from_index, to_index)

@router.get("/api/pages/{page_id}/image")
def get_page_image(page_id: str, type: str = "original", thumbnail: bool = False, preview: bool = False):
    return get_page_image_response(page_id, image_type=type, thumbnail=thumbnail, preview=preview)

@router.get("/api/pages/{page_id}/bubbles")
def get_bubbles(page_id: str):
    return get_bubbles_response(page_id)

@router.post("/api/pages/{page_id}/bubbles")
def update_bubbles(page_id: str, bubbles: List[BubbleUpdateSchema]):
    return update_bubbles_response(page_id, bubbles)

@router.post("/api/pages/{page_id}/bubbles/{bubble_id}/ocr")
def re_ocr_bubble(page_id: str, bubble_id: int):
    return re_ocr_bubble_response(page_id, bubble_id)

@router.post("/api/pages/{page_id}/bubbles/{bubble_id}/translate")
def translate_single_bubble(page_id: str, bubble_id: int):
    return start_translate_bubble(page_id, bubble_id)

@router.post("/api/pages/{page_id}/bubbles/{bubble_id}/inpaint")
def inpaint_single_bubble(page_id: str, bubble_id: int):
    return start_inpaint_bubble(page_id, bubble_id)

@router.post("/api/pages/{page_id}/inpaint")
def run_inpaint(page_id: str):
    return start_inpaint_page(page_id)

@router.post("/api/pages/{page_id}/translate-all")
def run_translate_all(page_id: str, container: AppContainer = Depends(get_container)):
    with container.legacy_state.lock:
        page_idx = _resolve_page_index(page_id)
    return container.job_manager.start(
        "auto-typeset",
        page_idx,
        f"auto-typeset:{page_id}",
        lambda job: container.auto_typeset_pipeline.run_page(job, page_id, show_progress=True),
    )

@router.post("/api/pages/translate-batch")
def run_translate_batch(req: TranslateBatchRequest, container: AppContainer = Depends(get_container)):
    """Translate multiple pages as a single batch job."""
    with container.legacy_state.lock:
        valid_indices = _resolve_indices_from_request(req)
        if not valid_indices:
            raise HTTPException(status_code=400, detail="No valid pages to translate")
        page_ids = [container.legacy_state.pages[idx].page_id for idx in valid_indices]
        first_idx = valid_indices[0]

    key = f"auto-typeset-batch:{','.join(page_ids)}"
    return container.job_manager.start(
        "auto-typeset-batch",
        first_idx,
        key,
        lambda job: container.auto_typeset_pipeline.run_batch(job, page_ids),
    )


@router.post("/api/pages/{page_id}/export")
def export_page(page_id: str, save_path: Optional[str] = Form(None), use_dialog: bool = Form(False)):
    return export_page_response(page_id, save_path=save_path)
