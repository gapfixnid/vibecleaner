from __future__ import annotations

from fastapi import HTTPException
from fastapi.responses import Response

from .page_crud import resolve_page
from ...infrastructure.image.loading import ensure_page_image
from .bubbles import get_bubbles_response


def get_text_layer_response(container, namespace: str, page_id: str, bubble_id: int, cache_key: str) -> Response:
    service = container.text_layer_service
    cache = container.text_layer_cache
    if namespace != service.namespace:
        raise HTTPException(status_code=410, detail={"code": "TEXT_LAYER_SESSION_EXPIRED"}, headers={"Cache-Control": "no-store"})

    cached = cache.find_by_public_key(namespace, page_id, bubble_id, cache_key)
    if cached is not None:
        return _tile_response(cached)

    state = container.project_state
    with state.lock:
        try:
            page = resolve_page(state, page_id)
        except Exception as exc:
            raise HTTPException(status_code=410, detail={"code": "TEXT_LAYER_EVICTED"}, headers={"Cache-Control": "no-store"}) from exc
        current_ref = page.text_layer_refs.get(bubble_id)
        if not current_ref or current_ref.get("cache_key") != cache_key:
            raise HTTPException(status_code=410, detail={"code": "TEXT_LAYER_EVICTED"}, headers={"Cache-Control": "no-store"})
        bubble = next((item.clone() for item in page.bubbles if item.id == bubble_id), None)
        if bubble is None:
            raise HTTPException(status_code=410, detail={"code": "TEXT_LAYER_EVICTED"}, headers={"Cache-Control": "no-store"})
        ensure_page_image(page)
        image = page.cv_image.copy()
        image_revision = page.image_visual_revision

    try:
        tile = service.create_tile(page_id, bubble, image, image_revision=image_revision)
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"code": "TEXT_LAYER_RENDER_FAILED"}, headers={"Cache-Control": "no-store"}) from exc
    if tile.cache_key != cache_key:
        raise HTTPException(status_code=410, detail={"code": "TEXT_LAYER_EVICTED"}, headers={"Cache-Control": "no-store"})
    return _tile_response(tile)


def _tile_response(tile) -> Response:
    return Response(
        content=tile.png_bytes,
        media_type="image/png",
        headers={
            "Cache-Control": "private, max-age=31536000, immutable",
            "ETag": f'"{tile.cache_key}"',
            "X-VibeCleaner-Text-Layer-Key": tile.cache_key,
            "X-Content-Type-Options": "nosniff",
        },
    )


def retry_text_layers_response(container, page_id: str, request) -> dict:
    state = container.project_state
    with state.lock:
        page = resolve_page(state, page_id)
        if state.project_generation != request.expected_project_generation:
            raise HTTPException(status_code=409, detail={"code": "PROJECT_REPLACED"})
        if page.visual_revision != request.expected_visual_revision:
            raise HTTPException(status_code=409, detail={"code": "VISUAL_REVISION_CONFLICT"})
        snapshot_page = page
        ensure_page_image(page)
        image = page.cv_image.copy()
        image_revision = page.image_visual_revision
        bubbles = [
            bubble.clone()
            for bubble in page.bubbles
            if bubble.id in request.bubble_ids
            and page.bubble_render_status.get(bubble.id, {}).get("status") == "fallback"
        ]

    recovered = {}
    for bubble in bubbles:
        try:
            tile = container.text_layer_service.create_tile(
                page_id, bubble, image, image_revision=image_revision
            )
            recovered[bubble.id] = {
                "layout_fingerprint": tile.layout_fingerprint,
                "render_fingerprint": tile.render_fingerprint,
                "cache_key": tile.cache_key,
                "pixel_digest": tile.pixel_digest,
                "crop_x": tile.crop_x,
                "crop_y": tile.crop_y,
                "width": tile.width,
                "height": tile.height,
            }
        except Exception:
            continue

    with state.lock:
        page = resolve_page(state, page_id)
        if state.project_generation != request.expected_project_generation:
            raise HTTPException(status_code=409, detail={"code": "PROJECT_REPLACED"})
        if page is not snapshot_page:
            raise HTTPException(status_code=409, detail={"code": "PAGE_REPLACED"})
        if page.visual_revision != request.expected_visual_revision:
            raise HTTPException(status_code=409, detail={"code": "VISUAL_REVISION_CONFLICT"})
        if recovered:
            for bubble_id, ref in recovered.items():
                page.text_layer_refs[bubble_id] = ref
                page.bubble_render_status[bubble_id] = {"status": "ready", "error_code": None}
            page.visual_revision += 1
        visual_revision = page.visual_revision

    snapshot = get_bubbles_response(
        state,
        page_id,
        container.render_service,
        container.text_layer_service,
    )
    return {
        "status": "ok",
        "page_id": page_id,
        "project_generation": state.project_generation,
        "content_revision": state.content_revision,
        "visual_revision": visual_revision,
        "text_layer_namespace": container.text_layer_service.namespace,
        "changed_bubbles": [bubble for bubble in snapshot["bubbles"] if bubble["id"] in recovered],
        "deleted_bubble_ids": [],
    }
