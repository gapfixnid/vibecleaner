from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Form
from pydantic import BaseModel

from ..dependencies import get_container
from ...core.container import AppContainer
from ...infrastructure.job_messages import msg
from ..use_cases.bubbles import (
    BubbleMutationRequest,
    BubbleUpdateSchema,
    VisualMutationPrecondition,
    get_bubbles_response,
    re_ocr_bubble_response,
    start_translate_bubble,
    update_bubbles_response,
)
from ..use_cases.page_images import get_page_image_response
from ..use_cases.page_text_layers import get_text_layer_response, retry_text_layers_response
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


class TextLayerRetryRequest(BaseModel):
    expected_project_generation: int
    expected_visual_revision: int
    bubble_ids: List[int]


class _BatchPageJobManager:
    """Map one page's pipeline progress into the enclosing batch job."""

    def __init__(
        self,
        job_manager: Any,
        *,
        page_offset: int,
        total_pages: int,
        ui_language: str,
    ) -> None:
        self._job_manager = job_manager
        self._page_offset = page_offset
        self._total_pages = max(1, total_pages)
        self._ui_language = ui_language

    def update(
        self,
        job: dict[str, Any],
        *,
        progress: int | None = None,
        message: str | None = None,
    ) -> None:
        mapped_progress = None
        if progress is not None:
            local_progress = max(0, min(100, progress))
            mapped_progress = int(
                ((self._page_offset * 100) + local_progress) / self._total_pages
            )

        page_message = msg(
            "batch_translation.translating_page",
            self._ui_language,
            current=self._page_offset + 1,
            total=self._total_pages,
        )
        combined_message = f"{page_message} {message}" if message else page_message
        self._job_manager.update(
            job,
            progress=mapped_progress,
            message=combined_message,
        )

    def ensure_not_cancelled(self, job: dict[str, Any]) -> None:
        self._job_manager.ensure_not_cancelled(job)


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
    return get_bubbles_response(
        container.project_state,
        page_id,
        container.render_service,
        container.text_layer_service,
    )


@router.get("/api/text-layers/{namespace}/{page_id}/{bubble_id}/{cache_key}.png")
def get_text_layer(
    namespace: str,
    page_id: str,
    bubble_id: int,
    cache_key: str,
    container: AppContainer = Depends(get_container),
):
    if bubble_id < 1 or bubble_id > 2**31 - 1:
        raise HTTPException(status_code=400, detail={"code": "INVALID_BUBBLE_ID"})
    if len(namespace) != 32 or any(ch not in "0123456789abcdef" for ch in namespace):
        raise HTTPException(status_code=400, detail={"code": "INVALID_TEXT_LAYER_NAMESPACE"})
    if len(cache_key) != 24 or any(ch not in "0123456789abcdef" for ch in cache_key):
        raise HTTPException(status_code=400, detail={"code": "INVALID_TEXT_LAYER_KEY"})
    return get_text_layer_response(container, namespace, page_id, bubble_id, cache_key)


@router.post("/api/pages/{page_id}/text-layers/retry")
def retry_text_layers(
    page_id: str,
    request: TextLayerRetryRequest,
    container: AppContainer = Depends(get_container),
):
    return retry_text_layers_response(container, page_id, request)

@router.post("/api/pages/{page_id}/bubbles")
def update_bubbles(
    page_id: str,
    request: BubbleMutationRequest,
    container: AppContainer = Depends(get_container),
):
    return update_bubbles_response(
        container.project_state,
        page_id,
        request,
        container.render_service,
        container.text_layer_service,
    )

@router.post("/api/pages/{page_id}/bubbles/{bubble_id}/ocr")
def re_ocr_bubble(
    page_id: str,
    bubble_id: int,
    precondition: VisualMutationPrecondition,
    container: AppContainer = Depends(get_container),
):
    return re_ocr_bubble_response(
        container.project_state,
        page_id,
        bubble_id,
        precondition,
        container.detection_service,
        container.config,
        container.text_layer_service,
    )

@router.post("/api/pages/{page_id}/bubbles/{bubble_id}/translate")
def translate_single_bubble(
    page_id: str,
    bubble_id: int,
    precondition: VisualMutationPrecondition,
    container: AppContainer = Depends(get_container),
):
    return start_translate_bubble(
        container.project_state,
        page_id,
        bubble_id,
        precondition,
        container.translation_service,
        container.config,
        container.job_manager,
        container.text_layer_service,
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
        page_job_manager = _BatchPageJobManager(
            container.job_manager,
            page_offset=attempted_pages,
            total_pages=total,
            ui_language=ui_lang,
        )
        try:
            with container.project_state.lock:
                page_idx = _resolve_page_index(container.project_state, page_id)
            page_job_manager.update(
                job,
                progress=0,
            )
            run_page_translation(
                job=job,
                page_id=page_id,
                state=container.project_state,
                config=container.config,
                job_manager=page_job_manager,
                runner=container.pipeline_runner,
                planner=container.pipeline_planner,
                show_progress=True,
            )
        except Exception as exc:
            if "cancelled" in str(exc).lower():
                raise
            error = str(exc.detail) if isinstance(exc, HTTPException) else str(exc)
            failed_page = {
                "page_id": page_id,
                "page_idx": page_idx,
                "error": error,
            }
            if hasattr(exc, "code"):
                failed_page.update({
                    "error_code": getattr(exc, "code"),
                    "error_stage": getattr(exc, "stage", None),
                    "retryable": bool(getattr(exc, "retryable", False)),
                    "error_details": dict(getattr(exc, "details", {}) or {}),
                })
            elif isinstance(getattr(exc, "detail", None), dict):
                detail = exc.detail
                failed_page.update({
                    "error_code": detail.get("code", "JOB_FAILED"),
                    "error_stage": detail.get("stage"),
                    "retryable": bool(detail.get("retryable", False)),
                    "error_details": dict(detail.get("details", {}) or {}),
                })
            failed_pages.append(failed_page)
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
            page_job_manager.update(job, progress=100)

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
    if failed_pages and "error_code" in failed_pages[0]:
        result.update({
            "error_code": failed_pages[0]["error_code"],
            "error_stage": failed_pages[0].get("error_stage"),
            "error_retryable": bool(failed_pages[0].get("retryable")),
            "error_details": failed_pages[0].get("error_details", {}),
        })
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
