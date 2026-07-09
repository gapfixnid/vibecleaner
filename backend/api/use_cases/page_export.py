import io
import os
from typing import Optional

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from core.models import MangaPage
from infrastructure.image.loading import ensure_page_image

from .page_crud import resolve_page


def export_page_response(state, page_id: str, export_service, save_path: Optional[str] = None):
    with state.lock:
        source = resolve_page(state, page_id)
        ensure_page_image(source)

        if source.inpainted_image is None:
            raise HTTPException(status_code=409, detail="Page must be cleaned before export")

        page = MangaPage(
            file_path=source.file_path,
            cv_image=source.cv_image.copy(),
            inpainted_image=source.inpainted_image.copy(),
            bubbles=[bubble.clone() for bubble in source.bubbles],
            bubble_counter=source.bubble_counter,
        )

    # Font path and per-bubble font resolution default to the export service's
    # bundled resolver; the API layer only names the family.
    pil_image = export_service.render_page(
        page,
        font_path=None,
        font_family="Pretendard Variable",
    )

    if pil_image is None:
        raise HTTPException(status_code=500, detail="Failed to render page image")

    if save_path:
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        pil_image.save(save_path)
        return {"status": "ok", "saved_path": save_path}

    buffer = io.BytesIO()
    pil_image.save(buffer, format="PNG")
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="image/png")
