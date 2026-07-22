from types import SimpleNamespace

import numpy as np
from backend.core.models import Rect

from backend.core.models import MangaPage, TextBubble
from backend.core.state.project_state import ProjectState
from backend.core.config import AppConfig
from backend.pipeline.page_translation import run_page_translation
from backend.pipeline.planner import PipelinePlanner
from backend.pipeline.page_translation_stages import build_page_translation_runner
from backend.infrastructure.jobs import JobManager
from backend.infrastructure.image.loading import invalidate_page_caches
from backend.api.use_cases.bubbles import get_bubbles_response

class FakeInpaintingService:
    def __init__(self):
        self.calls = []

    def clean_background(self, image, boxes, bubble_boxes, source_polygons=None, protect_edges=True, **_kwargs):
        self.calls.append({
            "boxes": boxes,
            "bubble_boxes": bubble_boxes,
            "source_polygons": source_polygons,
            "protect_edges": protect_edges,
        })
        cleaned = image.copy()
        cleaned[:, :] = 255
        return cleaned

class FakeTranslationService:
    def __init__(self):
        self.calls = []

    def translate_blocks(self, blocks, src_lang, tgt_lang, cv_image):
        self.calls.append({"texts": [block.text for block in blocks], "src_lang": src_lang, "tgt_lang": tgt_lang})
        for block in blocks:
            block.translation = f"translated:{block.text}"


class FakeRenderService:
    def __init__(self):
        self.calls = 0

    def get_layout_for_bubble(self, text, bubble, **_kwargs):
        self.calls += 1
        return SimpleNamespace(
            font=SimpleNamespace(pixelSize=lambda: 16, family=lambda: "Test Font"),
            is_overflow=False,
            reached_min_font=False,
            line_height_ratio=1.0,
            area_usage=0.5,
            line_layouts=[SimpleNamespace(
                text=text,
                x=bubble.box.x,
                y=bubble.box.y,
                width=bubble.box.width,
                height=16.0,
            )],
        )

def test_page_translation_runner_uses_canonical_stages_and_updates_page_state():
    state = ProjectState()
    config = AppConfig()
    page = MangaPage(
        file_path="sample.png",
        cv_image=np.zeros((24, 32, 3), dtype=np.uint8),
        bubbles=[
            TextBubble(
                id=1,
                box=Rect(2, 3, 10, 8),
                text_box=Rect(3, 4, 8, 6),
                text="hello",
                translated="",
            )
        ],
        bubble_counter=1,
    )
    page.page_id = "page_a"
    with state.lock:
        state.pages = [page]
        state.current_page_idx = 0
        state.revision = 0

    inpainting_service = FakeInpaintingService()
    translation_service = FakeTranslationService()
    render_service = FakeRenderService()
    runner = build_page_translation_runner(
        detection_service=SimpleNamespace(),
        inpainting_service=inpainting_service,
        translation_service=translation_service,
        page_analysis_service=SimpleNamespace(),
        bubble_analysis_service=SimpleNamespace(),
        layout_planner_service=SimpleNamespace(),
        render_service=render_service,
        ensure_page_image=lambda page: None,
        invalidate_page_caches=invalidate_page_caches,
        encode_preview_jpeg_bytes=lambda image: b"preview",
        encode_thumbnail_bytes=lambda image: b"thumb",
        refresh_page_status=lambda page: setattr(page, "status", "ready_for_review"),
    )

    result = run_page_translation(
        job={"cancel_requested": False},
        page_id="page_a",
        state=state,
        config=config,
        job_manager=JobManager(),
        runner=runner,
        planner=PipelinePlanner(),
        show_progress=False,
    )

    assert result == {"translated_count": 1}
    assert [stage.stage for stage in runner.last_result.context.provenance.stages] == [
        "detection",
        "ocr",
        "translation",
        "inpainting",
        "layout",
        "rendering",
    ]
    assert page.bubbles[0].translated == "translated:hello"
    assert page.status == "ready_for_review"
    assert page._preview_inpainted_bytes == b"preview"
    assert page._thumbnail_original_bytes == b"thumb"
    assert inpainting_service.calls[0]["boxes"] == [[3.0, 4.0, 11.0, 10.0]]
    assert render_service.calls == 1
    assert len(page._bubble_layout_cache) == 1

    response = get_bubbles_response(state, "page_a", render_service)

    assert render_service.calls == 1
    assert response["bubbles"][0]["translated"] == "translated:hello"
