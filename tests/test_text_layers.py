from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import cv2
import numpy as np

from backend.api.use_cases.bubbles import (
    BubbleMutationRequest,
    BubbleUpdateSchema,
    update_bubbles_response,
)
from backend.api.use_cases.page_text_layers import get_text_layer_response
from backend.core.models import MangaPage, Rect, TextBubble
from backend.core.state.project_state import ProjectState
from backend.engines.rendering.service import RenderService
from backend.engines.rendering.export import ExportService
from backend.engines.rendering.text_layer import TextLayerService
from backend.infrastructure.image.text_layer_cache import TextLayerCache
from backend.infrastructure.runtime.qt import get_qt_runtime


def make_service():
    runtime = get_qt_runtime()
    render = RenderService(executor=runtime.executor)
    cache = TextLayerCache()
    return runtime, render, TextLayerService(render, runtime.executor, cache, runtime.cache_namespace), cache


def make_bubble(color: str = "#000000") -> TextBubble:
    return TextBubble(
        id=1,
        box=Rect(20, 20, 200, 100),
        text="source",
        translated="hello 안녕",
        font_family="Pretendard Variable",
        font_size=24,
        color=color,
        text_class="text_free",
    )


def test_qt_worker_uses_explicit_dpr_one_metric_device():
    runtime = get_qt_runtime()
    worker_id, dpr = runtime.executor.run(
        lambda worker: (__import__("threading").get_ident(), worker.metric_device.devicePixelRatio())
    )
    assert worker_id == runtime.executor.thread_id
    assert dpr == 1.0


def test_tile_crop_uses_decoded_alpha_and_run_text_is_backend_resolved():
    _runtime, _render, service, _cache = make_service()
    image = np.full((200, 300, 3), 255, np.uint8)
    tile = service.create_tile("page_a", make_bubble(), image)
    decoded = cv2.imdecode(np.frombuffer(tile.png_bytes, np.uint8), cv2.IMREAD_UNCHANGED)

    assert decoded is not None and decoded.shape[2] == 4
    assert decoded.shape[:2] == (tile.height, tile.width)
    assert np.any(decoded[:, :, 3] > 0)
    assert np.any(decoded[0, :, 3] > 0) or np.any(decoded[-1, :, 3] > 0) or tile.height > 2
    assert tile.crop_x >= 0 and tile.crop_y >= 0
    assert tile.crop_x + tile.width <= image.shape[1]
    assert tile.crop_y + tile.height <= image.shape[0]
    assert "".join(run["text"] for run in tile.layout["lines"][0]["runs"]) == tile.layout["lines"][0]["text"]
    rgba = cv2.cvtColor(decoded, cv2.COLOR_BGRA2RGBA)
    expected_digest = hashlib.sha256(
        tile.width.to_bytes(4, "big") + tile.height.to_bytes(4, "big") + rgba.tobytes()
    ).hexdigest()
    assert tile.pixel_digest == expected_digest


def test_color_change_reuses_layout_identity_but_changes_render_identity():
    _runtime, _render, service, _cache = make_service()
    image = np.full((200, 300, 3), 255, np.uint8)
    black = service.create_tile("page_a", make_bubble("#000000"), image)
    red = service.create_tile("page_a", make_bubble("#ff0000"), image)

    assert black.layout_fingerprint == red.layout_fingerprint
    assert black.render_fingerprint != red.render_fingerprint
    assert black.pixel_digest != red.pixel_digest


def test_concurrent_same_tile_requests_share_one_cached_representation():
    _runtime, _render, service, cache = make_service()
    image = np.full((200, 300, 3), 255, np.uint8)
    with ThreadPoolExecutor(max_workers=4) as pool:
        tiles = list(pool.map(lambda _index: service.create_tile("page_a", make_bubble(), image), range(4)))

    assert len({tile.cache_key for tile in tiles}) == 1
    assert len({tile.png_bytes for tile in tiles}) == 1
    assert cache.current_bytes == len(tiles[0].png_bytes)


def test_historical_cached_tile_remains_immutable_after_current_ref_changes():
    runtime, render, service, cache = make_service()
    image = np.full((200, 300, 3), 255, np.uint8)
    old = service.create_tile("page_a", make_bubble("#000000"), image)
    new = service.create_tile("page_a", make_bubble("#ff0000"), image)
    page = MangaPage(file_path="sample.png", cv_image=image, bubbles=[make_bubble("#ff0000")], page_id="page_a")
    page.text_layer_refs[1] = {"cache_key": new.cache_key}
    state = ProjectState(pages=[page])
    container = SimpleNamespace(
        project_state=state,
        text_layer_service=service,
        text_layer_cache=cache,
        render_service=render,
        qt_runtime=runtime,
    )

    response = get_text_layer_response(container, service.namespace, "page_a", 1, old.cache_key)
    assert response.status_code == 200
    assert response.body == old.png_bytes
    assert response.headers["cache-control"].endswith("immutable")


def test_export_composites_the_same_cached_tile_pixels():
    _runtime, render, service, _cache = make_service()
    image = np.full((200, 300, 3), 255, np.uint8)
    bubble = make_bubble()
    page = MangaPage(
        file_path="sample.png",
        cv_image=image,
        inpainted_image=image.copy(),
        bubbles=[bubble],
        page_id="page_a",
    )
    tile = service.create_tile("page_a", bubble, image)

    exported = np.asarray(ExportService(render, service).render_page(page, None))
    tile_bgra = cv2.imdecode(np.frombuffer(tile.png_bytes, np.uint8), cv2.IMREAD_UNCHANGED)
    tile_rgba = cv2.cvtColor(tile_bgra, cv2.COLOR_BGRA2RGBA)
    alpha = tile_rgba[:, :, 3:4].astype(np.float32) / 255.0
    expected_rgb = np.rint(tile_rgba[:, :, :3] * alpha + 255.0 * (1.0 - alpha)).astype(np.uint8)
    crop = exported[tile.crop_y:tile.crop_y + tile.height, tile.crop_x:tile.crop_x + tile.width]

    assert np.max(np.abs(crop[:, :, :3].astype(np.int16) - expected_rgb.astype(np.int16))) <= 1
    assert np.all(crop[:, :, 3] == 255)


def test_tile_failure_commits_user_content_and_separates_revisions():
    runtime, render, _service, _cache = make_service()
    image = np.full((160, 240, 3), 255, np.uint8)
    page = MangaPage(file_path="sample.png", cv_image=image, bubbles=[make_bubble()], page_id="page_a")
    state = ProjectState(pages=[page], project_generation=3, content_revision=7)
    failing = SimpleNamespace(namespace="f" * 32, create_tile=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    request = BubbleMutationRequest(
        expected_project_generation=3,
        expected_visual_revision=0,
        bubbles=[BubbleUpdateSchema(
            id=1,
            x=20,
            y=20,
            width=200,
            height=100,
            text="source",
            translated="edited translation",
            font_family="Pretendard Variable",
            font_size=24,
            bold=False,
            italic=False,
            color="#000000",
            alignment="center",
        )],
    )

    result = update_bubbles_response(state, "page_a", request, render, failing)

    assert page.bubbles[0].translated == "edited translation"
    assert page.visual_revision == 1
    assert state.content_revision == 8
    assert result["changed_bubbles"][0]["render_status"]["status"] == "fallback"


def test_project_generation_only_changes_for_project_replacement():
    state = ProjectState()
    state.touch()
    assert state.project_generation == 0
    assert state.content_revision == 1
    state.replace_project()
    assert state.project_generation == 1
    assert state.content_revision == 2
