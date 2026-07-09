from __future__ import annotations

from ..context import PipelineContext
from .results import PipelineValidationError, ValidationIssue


def require_page_image(context: PipelineContext, stage: str) -> None:
    if context.image.width <= 0 or context.image.height <= 0:
        raise PipelineValidationError(
            [ValidationIssue(code="invalid_image", severity="error", message="page image is empty", stage=stage)]
        )