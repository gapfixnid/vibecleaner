from __future__ import annotations

from copy import deepcopy

from ..core.models.image import ImageData
from ..core.state.project_state import ProjectState
from .context import PipelineContext


def clone_page_translation_context(context: PipelineContext) -> PipelineContext:
    """Create an isolated page/project snapshot without copying runtime locks."""
    source_state = context.artifacts["state"]
    shadow_state = ProjectState(
        pages=deepcopy(source_state.pages),
        current_page_idx=source_state.current_page_idx,
        revision=source_state.revision,
        project_extensions=deepcopy(source_state.project_extensions),
    )
    artifacts = dict(context.artifacts)
    artifacts["state"] = shadow_state
    artifacts["job"] = dict(context.artifacts["job"])
    return PipelineContext(
        page_id=context.page_id,
        page=None,
        image=ImageData(array=None),
        settings=context.settings,
        artifacts=artifacts,
    )


def clone_page_translation_fallback_context(context: PipelineContext) -> PipelineContext:
    """Rebuild initial artifacts while retaining the real project state for v1 commit."""
    artifacts = {
        key: context.artifacts[key]
        for key in ("job", "show_progress", "state", "config", "job_manager")
    }
    return PipelineContext(
        page_id=context.page_id,
        page=None,
        image=ImageData(array=None),
        settings=context.settings,
        artifacts=artifacts,
    )
