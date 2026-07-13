from types import SimpleNamespace

import numpy as np

from backend.core.models.image import ImageData
from backend.core.models.page import MangaPage
from backend.core.state.project_state import ProjectState
from backend.pipeline.context import PipelineContext
from backend.pipeline.shadow import clone_page_translation_context


def test_page_shadow_snapshot_isolates_project_and_job_state():
    page = MangaPage(file_path="page.png", cv_image=np.zeros((2, 2, 3), dtype=np.uint8))
    state = ProjectState(pages=[page], current_page_idx=0, revision=4)
    context = PipelineContext(
        page_id=page.page_id,
        page=None,
        image=ImageData(array=None),
        settings=SimpleNamespace(),
        artifacts={
            "state": state,
            "job": {"cancel_requested": False},
            "job_manager": SimpleNamespace(),
            "config": SimpleNamespace(),
        },
    )
    shadow = clone_page_translation_context(context)
    shadow.artifacts["state"].pages[0].status = "shadow"
    shadow.artifacts["job"]["cancel_requested"] = True
    assert state.pages[0].status == "idle"
    assert context.artifacts["job"]["cancel_requested"] is False
    assert shadow.artifacts["state"].lock is not state.lock
