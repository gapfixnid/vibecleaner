import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from backend.core.config import AppConfig
from backend.core.models import MangaPage, Rect, TextBubble
from backend.core.models.image import ImageData
from backend.core.state.project_state import ProjectState
from backend.pipeline.context import PipelineContext
from backend.pipeline.page_translation_stages import PageDetectionStage
from backend.pipeline.planner import PipelinePlanner


FIXTURE = Path(__file__).parent / "fixtures" / "pipeline_v1" / "contract.json"


class RecordingDetectionService:
    def __init__(self):
        self.calls = []

    def detect_and_ocr(self, image, *, lang):
        self.calls.append({"image": image, "lang": lang})
        return [SimpleNamespace(text="detected")]


class NeverCancelledJobManager:
    def ensure_not_cancelled(self, job):
        return None


def _context_for(page: MangaPage) -> tuple[PipelineContext, ProjectState]:
    state = ProjectState(pages=[page], current_page_idx=0)
    context = PipelineContext(
        page_id=page.page_id,
        page=page,
        image=ImageData(array=None),
        settings=AppConfig(),
        artifacts={
            "state": state,
            "job": {"cancel_requested": False},
            "job_manager": NeverCancelledJobManager(),
            "show_progress": False,
            "config": AppConfig(source_language="Japanese"),
        },
    )
    return context, state


def test_v1_plan_matches_the_frozen_stage_contract():
    contract = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert PipelinePlanner().translate_page_plan().stages == contract["stages"]


def test_v1_empty_page_uses_the_combined_detection_and_ocr_entrypoint():
    service = RecordingDetectionService()
    page = MangaPage(
        file_path="sample.png",
        page_id="page-empty",
        cv_image=np.zeros((12, 16, 3), dtype=np.uint8),
    )
    context, _ = _context_for(page)

    result = PageDetectionStage(service, ensure_page_image=lambda current: None).run(context)

    assert len(service.calls) == 1
    assert service.calls[0]["lang"] == "Japanese"
    assert result.artifacts["blocks"][0].text == "detected"
    assert result.artifacts["local_bubbles"] == []


def test_v1_existing_bubbles_preserve_user_work_and_skip_detection():
    service = RecordingDetectionService()
    bubble = TextBubble(
        id=1,
        box=Rect(1, 1, 8, 8),
        text_box=Rect(2, 2, 6, 6),
        text="manual OCR",
        translated="manual translation",
    )
    page = MangaPage(
        file_path="sample.png",
        page_id="page-edited",
        cv_image=np.zeros((12, 16, 3), dtype=np.uint8),
        bubbles=[bubble],
        bubble_counter=1,
    )
    context, _ = _context_for(page)

    result = PageDetectionStage(service, ensure_page_image=lambda current: None).run(context)

    assert service.calls == []
    assert result.artifacts["local_bubbles"][0].text == "manual OCR"
    assert result.artifacts["local_bubbles"][0].translated == "manual translation"
    assert result.artifacts["local_bubbles"][0] is not bubble
