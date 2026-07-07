from __future__ import annotations

from dataclasses import dataclass, field

from pipeline.context import PipelineContext
from pipeline.plan import PipelinePlan
from pipeline.registry import StageRegistry
from pipeline.validation.results import PipelineValidationError, ValidationIssue


@dataclass
class PipelineResult:
    context: PipelineContext
    succeeded: bool
    issues: list[ValidationIssue] = field(default_factory=list)


class PipelineRunner:
    def __init__(self, registry: StageRegistry) -> None:
        self.registry = registry

    def run(self, context: PipelineContext, plan: PipelinePlan) -> PipelineResult:
        context.provenance.page_id = context.page_id
        for stage_name in plan.stages:
            stage = self.registry.get(stage_name)
            entry, started_at = context.provenance.start_stage(
                stage_name,
                input_summary={"artifact_count": len(context.artifacts)},
            )
            try:
                context = stage.run(context)
            except PipelineValidationError as exc:
                context.provenance.finish_stage(
                    entry,
                    started_at,
                    output_summary={"artifact_count": len(context.artifacts)},
                    errors=[issue.message for issue in exc.issues],
                )
                return PipelineResult(context=context, succeeded=False, issues=exc.issues)

            context.provenance.finish_stage(
                entry,
                started_at,
                output_summary={"artifact_count": len(context.artifacts)},
            )

        return PipelineResult(context=context, succeeded=True)
