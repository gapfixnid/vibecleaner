from __future__ import annotations

from typing import Any

from ..core.models.image import ImageData
from .context import PipelineContext


def run_page_translation(
    *,
    job: dict,
    page_id: str,
    state: Any,
    config: Any,
    job_manager: Any,
    runner: Any,
    planner: Any,
    show_progress: bool = True,
) -> dict[str, int]:
    context = PipelineContext(
        page_id=page_id,
        page=None,
        image=ImageData(array=None),
        settings=config,
        artifacts={
            "job": job,
            "show_progress": show_progress,
            "state": state,
            "config": config,
            "job_manager": job_manager,
        },
    )
    result = runner.run(context, planner.translate_page_plan())
    runner.last_result = result
    if not result.succeeded:
        message = result.issues[0].message if result.issues else "Page translation pipeline failed"
        raise RuntimeError(message)
    return result.context.artifacts["result"]