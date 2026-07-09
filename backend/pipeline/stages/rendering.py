from __future__ import annotations

from ...core.ports.rendering import Renderer
from ..context import PipelineContext
from ..strategies.engine_selection import EngineSelectionStrategy
from ..validation.results import PipelineValidationError, ValidationIssue


class RenderingStage:
    name = "rendering"

    def __init__(self, renderer: Renderer, strategy: EngineSelectionStrategy) -> None:
        self.renderer = renderer
        self.strategy = strategy

    def run(self, context: PipelineContext) -> PipelineContext:
        bubbles = context.artifacts.get("layout_result")
        if bubbles is None:
            raise PipelineValidationError(
                [ValidationIssue(code="missing_layout", severity="error", message="layout result missing", stage=self.name)]
            )
        options = self.strategy.render_options(context.settings)
        context.artifacts["render_result"] = self.renderer.render(context.image, bubbles, options)
        context.image = context.artifacts["render_result"].image
        return context