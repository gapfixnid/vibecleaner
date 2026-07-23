from __future__ import annotations

import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from backend.api.use_cases.bubbles import (
    BubbleMutationRequest,
    BubbleUpdateSchema,
    update_bubbles_response,
)
from backend.api.use_cases.page_text_layers import get_text_layer_response
from backend.core.models import MangaPage, Rect, TextBubble
from backend.core.state.project_state import ProjectState
from backend.engines.rendering.service import RenderService
from backend.engines.rendering.canonical_layout import (
    _expanded_alpha,
)
from backend.engines.rendering.alpha import compose_final_alpha
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
    paint_count = 0
    paint_lock = threading.Lock()
    original_paint = service._paint_artifact

    def counted_paint(*args, **kwargs):
        nonlocal paint_count
        with paint_lock:
            paint_count += 1
        return original_paint(*args, **kwargs)

    service._paint_artifact = counted_paint
    with ThreadPoolExecutor(max_workers=4) as pool:
        tiles = list(pool.map(lambda _index: service.create_tile("page_a", make_bubble(), image), range(4)))

    assert len({tile.cache_key for tile in tiles}) == 1
    assert len({tile.png_bytes for tile in tiles}) == 1
    assert cache.current_bytes == len(tiles[0].png_bytes)
    assert paint_count == 1


def test_cached_canonical_alpha_is_owned_contiguous_and_read_only():
    _runtime, _render, service, _cache = make_service()
    image = np.full((200, 300, 3), 255, np.uint8)
    bubble = make_bubble()
    request = service.canonical_selector.build_request(
        bubble.translated,
        bubble,
        image,
        bubble.font_family,
    )
    artifact = service.canonical_selector.get_artifact(request)

    for alpha in (
        artifact.selected.fill_alpha,
        artifact.selected.stroke_only_alpha,
    ):
        assert alpha.flags.c_contiguous
        assert not alpha.flags.writeable
        assert alpha.base is None

    fill = artifact.selected.fill_alpha
    stroke = artifact.selected.stroke_only_alpha
    expected = np.maximum(
        _expanded_alpha(
            fill,
            max(
                1.0,
                artifact.selected.candidate.effective_font_size
                / 12.0,
            ),
        ).astype(np.int16)
        - fill.astype(np.int16),
        0,
    ).astype(np.uint8)
    assert np.array_equal(stroke, expected)
    assert not np.any((fill == 255) & (stroke > 0))


def test_empty_candidate_set_returns_serializable_overflow_layout(
    monkeypatch,
):
    _runtime, render, service, _cache = make_service()
    image = np.full((80, 120, 3), 255, np.uint8)
    bubble = TextBubble(
        id=9,
        box=Rect(10, 10, 18, 12),
        text="source",
        translated="a very long translated sentence",
        text_class="text_free",
    )
    selector = service.canonical_selector
    monkeypatch.setattr(
        selector, "_collect_candidates", lambda _request: []
    )

    layout = render.get_layout_for_bubble(
        bubble.translated, bubble, image
    )

    assert layout.is_overflow
    assert layout.line_layouts


def test_resource_exhaustion_keeps_overflow_layout_for_dom_fallback(
    monkeypatch,
):
    _runtime, render, service, _cache = make_service()
    image = np.full((80, 120, 3), 255, np.uint8)
    bubble = TextBubble(
        id=10,
        box=Rect(10, 10, 40, 20),
        text="source",
        translated="translated",
        text_class="text_free",
    )
    selector = service.canonical_selector
    monkeypatch.setattr(
        selector,
        "_rasterize_candidate",
        lambda _worker, _request, candidate, **_kwargs: (
            selector._resource_failure(candidate)
        ),
    )

    layout = render.get_layout_for_bubble(
        bubble.translated, bubble, image
    )

    assert layout.is_overflow
    assert layout.line_layouts
    assert (
        layout.diagnostics["error_code"]
        == "CANONICAL_LAYOUT_RESOURCE_EXHAUSTED"
    )


def test_public_layout_uses_same_shaped_geometry_as_tile_artifact():
    _runtime, _render, service, _cache = make_service()
    image = np.full((200, 300, 3), 255, np.uint8)
    bubble = make_bubble()
    request = service.canonical_selector.build_request(
        bubble.translated, bubble, image, bubble.font_family
    )
    artifact = service.canonical_selector.get_artifact(request)

    public = artifact.public_layout.line_layouts[0]
    shaped = artifact.selected.shaped_lines[0]
    assert public.origin_x == shaped.origin_x
    assert public.baseline_y == shaped.baseline_y
    assert public.ink_left == shaped.ink_left
    assert public.runs == shaped.runs


def test_final_alpha_helper_matches_source_over_contract():
    fill = np.array([[0, 128, 255]], dtype=np.uint8)
    stroke = np.array([[255, 128, 30]], dtype=np.uint8)
    expected = (
        fill.astype(np.uint16)
        + stroke.astype(np.uint16)
        * (255 - fill.astype(np.uint16))
        // 255
    ).astype(np.uint8)
    assert np.array_equal(
        compose_final_alpha(fill, stroke), expected
    )


def test_rect_auto_layout_rasters_both_break_passes_with_style():
    _runtime, _render, service, _cache = make_service()
    image = np.full((180, 280, 3), 255, np.uint8)
    bubble = TextBubble(
        id=11,
        box=Rect(20, 20, 180, 80),
        text="source",
        translated="styled rectangular automatic layout",
        font_family="Pretendard Variable",
        font_size=0,
        bold=True,
        italic=True,
        text_class="text_free",
    )
    request = service.canonical_selector.build_request(
        bubble.translated, bubble, image, bubble.font_family
    )
    artifact = service.canonical_selector.get_artifact(request)

    assert artifact.diagnostics["candidate_count"] >= 2
    assert artifact.selected.candidate.bold
    assert artifact.selected.candidate.italic


def test_unsafe_layout_is_dom_fallback_not_ready_png(
    monkeypatch,
):
    _runtime, render, service, _cache = make_service()
    image = np.full((180, 280, 3), 255, np.uint8)
    bubble = TextBubble(
        id=12,
        box=Rect(20, 20, 180, 80),
        text="source",
        translated="unsafe candidate",
        text_class="text_free",
    )
    selector = service.canonical_selector
    original = selector._rasterize_candidate

    def force_unsafe(*args, **kwargs):
        rasterized = original(*args, **kwargs)
        return replace(
            rasterized,
            diagnostics=replace(
                rasterized.diagnostics,
                raster_safe=False,
                outside_alpha_ratio=0.5,
            ),
        )

    monkeypatch.setattr(
        selector, "_rasterize_candidate", force_unsafe
    )
    layout = render.get_layout_for_bubble(
        bubble.translated, bubble, image
    )

    assert layout.is_overflow
    assert (
        layout.diagnostics["selected_pass"]
        == "overflow_fallback"
    )
    with pytest.raises(
        RuntimeError, match="TEXT_LAYER_LAYOUT_UNSAFE"
    ):
        service.create_tile("page_a", bubble, image)


def test_final_key_uses_explicit_forbidden_break_field():
    _runtime, _render, service, _cache = make_service()
    image = np.full((180, 280, 3), 255, np.uint8)
    bubble = TextBubble(
        id=13,
        box=Rect(20, 20, 180, 80),
        text="source",
        translated="rect candidate",
        text_class="text_free",
    )
    request = service.canonical_selector.build_request(
        bubble.translated, bubble, image, None
    )
    artifact = service.canonical_selector.get_artifact(request)
    selected = artifact.selected
    clean = replace(
        selected,
        candidate=replace(
            selected.candidate,
            forbidden_break_count=0,
            rough_key=(False, 0.0, -12, 999.0),
        ),
    )
    forbidden = replace(
        selected,
        candidate=replace(
            selected.candidate,
            forbidden_break_count=1,
            rough_key=(False, 0.0, -12, 0.0),
        ),
    )

    assert (
        service.canonical_selector._final_key(clean)
        < service.canonical_selector._final_key(forbidden)
    )


def test_executor_reentry_is_rejected_instead_of_deadlocking():
    runtime = get_qt_runtime()
    try:
        runtime.executor.run(
            lambda _worker: runtime.executor.run(lambda _nested: None)
        )
    except RuntimeError as exc:
        assert "deadlock" in str(exc).lower()
    else:
        raise AssertionError("nested synchronous render was accepted")


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
