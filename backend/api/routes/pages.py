from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Form
from pydantic import BaseModel

from ..dependencies import get_container
from ...core.container import AppContainer
from ...infrastructure.job_messages import msg
from ..use_cases.bubbles import (
    BubbleUpdateSchema,
    get_bubbles_response,
    re_ocr_bubble_response,
    start_translate_bubble,
    update_bubbles_response,
)
from ..use_cases.page_images import get_page_image_response
from ..use_cases.page_crud import (
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
from ..use_cases.page_export import export_page_response
from ..use_cases.page_inpaint import start_inpaint_bubble, start_inpaint_page
from ...pipeline.page_translation import run_page_translation
router = APIRouter()


class TranslateBatchRequest(BaseModel):
    page_indices: Optional[List[int]] = None
    page_ids: Optional[List[str]] = None

@router.get("/api/pages")
def get_pages(container: AppContainer = Depends(get_container)):
    return get_pages_response(container.project_state)

@router.post("/api/pages/select")
def select_page(
    index: Optional[int] = Form(None),
    page_id: Optional[str] = Form(None),
    container: AppContainer = Depends(get_container),
):
    return select_page_response(container.project_state, index=index, page_id=page_id)

@router.post("/api/pages/{page_id}/rename")
def rename_page(page_id: str, name: str = Form(...), container: AppContainer = Depends(get_container)):
    return rename_page_response(container.project_state, page_id, name)


@router.post("/api/pages/duplicate")
def duplicate_page(
    index: Optional[int] = Form(None),
    page_id: Optional[str] = Form(None),
    container: AppContainer = Depends(get_container),
):
    return duplicate_page_response(container.project_state, index=index, page_id=page_id)


@router.post("/api/pages/duplicate-batch")
def duplicate_page_batch(req: TranslateBatchRequest, container: AppContainer = Depends(get_container)):
    return duplicate_page_batch_response(container.project_state, req)


@router.post("/api/pages/delete")
def delete_page(
    index: Optional[int] = Form(None),
    page_id: Optional[str] = Form(None),
    container: AppContainer = Depends(get_container),
):
    return delete_page_response(container.project_state, index=index, page_id=page_id)


@router.post("/api/pages/delete-batch")
def delete_page_batch(req: TranslateBatchRequest, container: AppContainer = Depends(get_container)):
    return delete_page_batch_response(container.project_state, req)

@router.post("/api/pages/reorder")
def reorder_pages(
    from_index: int = Form(...),
    to_index: int = Form(...),
    container: AppContainer = Depends(get_container),
):
    return reorder_pages_response(container.project_state, from_index, to_index)

@router.get("/api/pages/{page_id}/image")
def get_page_image(
    page_id: str,
    type: str = "original",
    thumbnail: bool = False,
    preview: bool = False,
    container: AppContainer = Depends(get_container),
):
    return get_page_image_response(container.project_state, page_id, image_type=type, thumbnail=thumbnail, preview=preview)

@router.get("/api/pages/{page_id}/bubbles")
def get_bubbles(page_id: str, container: AppContainer = Depends(get_container)):
    return get_bubbles_response(container.project_state, page_id, container.render_service)

@router.post("/api/pages/{page_id}/bubbles")
def update_bubbles(
    page_id: str,
    bubbles: List[BubbleUpdateSchema],
    container: AppContainer = Depends(get_container),
):
    return update_bubbles_response(container.project_state, page_id, bubbles)

@router.post("/api/pages/{page_id}/bubbles/{bubble_id}/ocr")
def re_ocr_bubble(page_id: str, bubble_id: int, container: AppContainer = Depends(get_container)):
    return re_ocr_bubble_response(container.project_state, page_id, bubble_id, container.detection_service, container.config)

@router.post("/api/pages/{page_id}/bubbles/{bubble_id}/translate")
def translate_single_bubble(page_id: str, bubble_id: int, container: AppContainer = Depends(get_container)):
    return start_translate_bubble(
        container.project_state,
        page_id,
        bubble_id,
        container.translation_service,
        container.config,
        container.job_manager,
    )

@router.post("/api/pages/{page_id}/bubbles/{bubble_id}/inpaint")
def inpaint_single_bubble(page_id: str, bubble_id: int, container: AppContainer = Depends(get_container)):
    return start_inpaint_bubble(
        container.project_state, page_id, bubble_id, container.inpainting_service, container.job_manager, container.config
    )

@router.post("/api/pages/{page_id}/inpaint")
def run_inpaint(page_id: str, container: AppContainer = Depends(get_container)):
    return start_inpaint_page(container.project_state, page_id, container.inpainting_service, container.job_manager, container.config)

@router.post("/api/pages/{page_id}/translate-all")
def run_translate_all(page_id: str, container: AppContainer = Depends(get_container)):
    with container.project_state.lock:
        page_idx = _resolve_page_index(container.project_state, page_id)
    return container.job_manager.start(
        "page-translation",
        page_idx,
        f"page-translation:{page_id}",
        lambda job: run_page_translation(
            job=job,
            page_id=page_id,
            state=container.project_state,
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
    with container.project_state.lock:
        valid_indices = _resolve_indices_from_request(container.project_state, req)
        if not valid_indices:
            raise HTTPException(status_code=400, detail="No valid pages to translate")
        page_ids = [container.project_state.pages[idx].page_id for idx in valid_indices]
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
    attempted_pages = 0
    successful_page_indices: list[int] = []
    failed_pages: list[dict[str, object]] = []
    ui_lang = container.config.ui_language

    for page_id in page_ids:
        page_idx = None
        try:
            with container.project_state.lock:
                page_idx = _resolve_page_index(container.project_state, page_id)
            container.job_manager.update(
                job,
                progress=int((attempted_pages / total) * 100),
                message=msg("batch_translation.translating_page", ui_lang, current=attempted_pages + 1, total=total),
            )
            run_page_translation(
                job=job,
                page_id=page_id,
                state=container.project_state,
                config=container.config,
                job_manager=container.job_manager,
                runner=container.pipeline_runner,
                planner=container.pipeline_planner,
                show_progress=False,
            )
        except Exception as exc:
            if "cancelled" in str(exc).lower():
                raise
            error = str(exc.detail) if isinstance(exc, HTTPException) else str(exc)
            failed_pages.append({"page_id": page_id, "page_idx": page_idx, "error": error})
        else:
            if page_idx is not None:
                successful_page_indices.append(page_idx)
        finally:
            attempted_pages += 1
            job["result"] = {
                "successful_pages": len(successful_page_indices),
                "total_pages": total,
                "successful_page_indices": list(successful_page_indices),
                "failed_pages": list(failed_pages),
            }

        container.job_manager.ensure_not_cancelled(job)

    if failed_pages and successful_page_indices:
        status = "succeeded_with_errors"
    elif failed_pages:
        status = "failed"
    else:
        status = "succeeded"

    result = {
        "status": status,
        "successful_pages": len(successful_page_indices),
        "total_pages": total,
        "successful_page_indices": successful_page_indices,
        "failed_pages": failed_pages,
    }
    container.job_manager.update(job, progress=100, message=msg("batch_translation.complete", ui_lang))
    return result


@router.post("/api/pages/{page_id}/export")
def export_page(
    page_id: str,
    save_path: Optional[str] = Form(None),
    use_dialog: bool = Form(False),
    container: AppContainer = Depends(get_container),
):
    return export_page_response(container.project_state, page_id, container.export_service, save_path=save_path)
