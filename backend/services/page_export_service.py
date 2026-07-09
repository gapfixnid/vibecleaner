import io
import os
from functools import lru_cache
from typing import Optional

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from core.models import MangaPage
from services.page_crud_service import resolve_page
from services.page_image_loader import ensure_page_image


@lru_cache(maxsize=64)
def resolve_font_path(font_family: str | None) -> str | None:
    from infrastructure.fonts import resolver as font_resolver

    resolved, _chain = font_resolver.resolve(
        text="",
        requested_family=font_family,
        target_lang="Korean",
    )
    return resolved.path


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

    font_path = resolve_font_path("Pretendard Variable")

    pil_image = export_service.render_page(
        page,
        font_path=font_path,
        font_family="Pretendard Variable",
        font_resolver=resolve_font_path,
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
