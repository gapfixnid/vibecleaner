from __future__ import annotations

from dataclasses import dataclass

from .context import PipelineContext
from .registry import StageRegistry
from .runner import PipelineResult
from .validation.results import PipelineValidationError


@dataclass(frozen=True)
class DagStage:
    name: str
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class DagPipelinePlan:
    stages: tuple[DagStage, ...]

    def validate(self) -> None:
        names = {stage.name for stage in self.stages}
        if len(names) != len(self.stages):
            raise ValueError("DAG contains duplicate stage names")
        for stage in self.stages:
            missing = set(stage.depends_on) - names
            if missing:
                raise ValueError(f"Stage {stage.name} depends on unknown stages: {sorted(missing)}")
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(name: str) -> None:
            if name in visiting:
                raise ValueError("DAG contains a dependency cycle")
            if name in visited:
                return
            visiting.add(name)
            stage = next(item for item in self.stages if item.name == name)
            for dependency in stage.depends_on:
                visit(dependency)
            visiting.remove(name)
            visited.add(name)

        for stage in self.stages:
            visit(stage.name)


class DagPipelineExecutor:
    """Deterministic v2 DAG executor; parallel scheduling is a later optimization."""

    def __init__(self, registry: StageRegistry) -> None:
        self.registry = registry

    def run(self, context: PipelineContext, plan: DagPipelinePlan) -> PipelineResult:
        plan.validate()
        completed: set[str] = set()
        pending = list(plan.stages)
        while pending:
            ready = [stage for stage in pending if set(stage.depends_on) <= completed]
            if not ready:
                raise ValueError("DAG could not make progress")
            for spec in ready:
                stage = self.registry.get(spec.name)
                entry, started_at = context.provenance.start_stage(
                    spec.name, input_summary={"artifact_count": len(context.artifacts)}
                )
                try:
                    context = stage.run(context)
                except PipelineValidationError as exc:
                    context.provenance.finish_stage(
                        entry, started_at,
                        output_summary={"artifact_count": len(context.artifacts)},
                        errors=[issue.message for issue in exc.issues],
                    )
                    return PipelineResult(context=context, succeeded=False, issues=exc.issues)
                context.provenance.finish_stage(
                    entry, started_at, output_summary={"artifact_count": len(context.artifacts)}
                )
                completed.add(spec.name)
                pending.remove(spec)
        return PipelineResult(context=context, succeeded=True)
