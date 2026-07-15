import os
from copy import deepcopy
from typing import List

from fastapi import HTTPException
from PIL import Image

from ...core.models import MangaPage
from ...infrastructure.image.loading import ensure_page_image
from ...core.state.review import derive_page_status


def get_page_by_id(state, page_id: str) -> MangaPage:
    for page in state.pages:
        if page.page_id == page_id:
            return page
    raise HTTPException(status_code=404, detail="Page not found")


def get_page_index_by_id(state, page_id: str) -> int:
    for idx, page in enumerate(state.pages):
        if page.page_id == page_id:
            return idx
    raise HTTPException(status_code=404, detail="Page not found")


def resolve_page(state, page_id: str) -> MangaPage:
    if page_id.isdigit():
        idx = int(page_id)
        if 0 <= idx < len(state.pages):
            return state.pages[idx]
        raise HTTPException(status_code=404, detail="Page not found")
    return get_page_by_id(state, page_id)


def resolve_page_index(state, page_id: str) -> int:
    if page_id.isdigit():
        idx = int(page_id)
        if 0 <= idx < len(state.pages):
            return idx
        raise HTTPException(status_code=404, detail="Page not found")
    return get_page_index_by_id(state, page_id)


def resolve_indices_from_request(state, req) -> List[int]:
    indices = []
    if req.page_ids:
        for page_id in req.page_ids:
            try:
                indices.append(resolve_page_index(state, page_id))
            except HTTPException:
                pass
    if req.page_indices:
        for idx in req.page_indices:
            if 0 <= idx < len(state.pages) and idx not in indices:
                indices.append(idx)
    return indices


def get_pages_response(state):
    with state.lock:
        pages_list = []
        for idx, page in enumerate(state.pages):
            width = getattr(page, "_width", 0)
            height = getattr(page, "_height", 0)
            if width == 0 or height == 0:
                if page.cv_image is not None and page.cv_image.size > 0:
                    height, width = page.cv_image.shape[:2]
                else:
                    try:
                        with Image.open(page.file_path) as img:
                            width, height = img.size
                        page._width = width
                        page._height = height
                    except Exception:
                        width, height = 100, 100
            pages_list.append({
                "page_id": page.page_id,
                "index": idx,
                "file_path": page.file_path,
                "filename": page.display_name or os.path.basename(page.file_path),
                "width": width,
                "height": height,
                "status": derive_page_status(page),
                "problems": list(page.problems),
                "bubble_count": len(page.bubbles),
                "translated_count": sum(1 for b in page.bubbles if (b.translated or "").strip()),
                "has_inpaint": page.inpainted_image is not None,
            })
        return {"pages": pages_list, "current_index": state.current_page_idx}


def select_page_response(state, index=None, page_id=None):
    with state.lock:
        if page_id is not None:
            index = get_page_index_by_id(state, page_id)
        elif index is None:
            raise HTTPException(status_code=400, detail="Either index or page_id must be provided")

        if index < 0 or index >= len(state.pages):
            raise HTTPException(status_code=404, detail="Page index out of bounds")
        state.current_page_idx = index
        return {"status": "ok", "current_index": state.current_page_idx}


def rename_page_response(state, page_id: str, name: str):
    cleaned = (name or "").strip().replace("/", "").replace("\\", "")
    if not cleaned:
        raise HTTPException(status_code=400, detail="Name must not be empty")

    with state.lock:
        page = resolve_page(state, page_id)
        current = page.display_name or os.path.basename(page.file_path)
        ext = os.path.splitext(current)[1]
        page.display_name = f"{cleaned}{ext}"
        state.touch()
        return {"status": "ok", "filename": page.display_name}


def _clone_page(source: MangaPage) -> MangaPage:
    ensure_page_image(source)
    clone = MangaPage(
        file_path=source.file_path,
        cv_image=source.cv_image.copy(),
        inpainted_image=source.inpainted_image.copy() if source.inpainted_image is not None else None,
        bubbles=[bubble.clone() for bubble in source.bubbles],
        bubble_counter=source.bubble_counter,
        project_extensions=deepcopy(source.project_extensions),
    )
    clone._width = getattr(source, "_width", 0)
    clone._height = getattr(source, "_height", 0)
    clone._loaded = getattr(source, "_loaded", True)
    if getattr(source, "_thumbnail_original_bytes", None) is not None:
        clone._thumbnail_original_bytes = source._thumbnail_original_bytes
    return clone


def duplicate_page_response(state, index=None, page_id=None):
    with state.lock:
        if page_id is not None:
            index = resolve_page_index(state, page_id)
        elif index is None:
            raise HTTPException(status_code=400, detail="Either index or page_id must be provided")
        if index < 0 or index >= len(state.pages):
            raise HTTPException(status_code=404, detail="Page index out of bounds")
        state.pages.insert(index + 1, _clone_page(state.pages[index]))
        state.current_page_idx = index + 1
        state.touch()
        return {"status": "ok", "current_index": state.current_page_idx}


def duplicate_page_batch_response(state, req):
    with state.lock:
        valid_indices = sorted(set(resolve_indices_from_request(state, req)))
        if not valid_indices:
            raise HTTPException(status_code=400, detail="No valid pages to duplicate")
        for idx in sorted(valid_indices, reverse=True):
            state.pages.insert(idx + 1, _clone_page(state.pages[idx]))
        state.current_page_idx = valid_indices[0] + 1
        state.touch()
        return {
            "status": "ok",
            "current_index": state.current_page_idx,
            "duplicated_count": len(valid_indices),
        }


def _clamp_current_index(state) -> None:
    if state.current_page_idx >= len(state.pages):
        state.current_page_idx = len(state.pages) - 1


def delete_page_response(state, index=None, page_id=None):
    with state.lock:
        if page_id is not None:
            index = resolve_page_index(state, page_id)
        elif index is None:
            raise HTTPException(status_code=400, detail="Either index or page_id must be provided")
        if index < 0 or index >= len(state.pages):
            raise HTTPException(status_code=404, detail="Page index out of bounds")
        state.pages.pop(index)
        _clamp_current_index(state)
        state.touch()
        return {"status": "ok", "current_index": state.current_page_idx}


def delete_page_batch_response(state, req):
    with state.lock:
        valid_indices = resolve_indices_from_request(state, req)
        if not valid_indices:
            raise HTTPException(status_code=400, detail="No valid pages to delete")
        for idx in sorted(set(valid_indices), reverse=True):
            state.pages.pop(idx)
        _clamp_current_index(state)
        state.touch()
        return {"status": "ok", "current_index": state.current_page_idx, "deleted_count": len(valid_indices)}


def reorder_pages_response(state, from_index: int, to_index: int):
    with state.lock:
        if from_index < 0 or from_index >= len(state.pages) or to_index < 0 or to_index >= len(state.pages):
            raise HTTPException(status_code=404, detail="Indices out of bounds")
        page = state.pages.pop(from_index)
        state.pages.insert(to_index, page)
        if state.current_page_idx == from_index:
            state.current_page_idx = to_index
        elif from_index < state.current_page_idx <= to_index:
            state.current_page_idx -= 1
        elif to_index <= state.current_page_idx < from_index:
            state.current_page_idx += 1
        state.touch()
        return {"status": "ok", "current_index": state.current_page_idx}
