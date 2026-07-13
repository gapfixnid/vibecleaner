from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from time import sleep

from .context import PipelineContext
from .checkpoint import CheckpointManifest
from .registry import StageRegistry
from .runner import PipelineResult
from .resources import ResourceClass, ResourceManager
from .validation.results import PipelineValidationError, ValidationIssue


@dataclass(frozen=True)
class DagStage:
    name: str
    depends_on: tuple[str, ...] = ()
    resource: ResourceClass = ResourceClass.CPU
    max_retries: int = 0


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

    def __init__(self, registry: StageRegistry, resource_manager: ResourceManager | None = None, checkpoint_store: Any | None = None, retry_backoff_seconds: float = 0.25) -> None:
        self.registry = registry
        self.resource_manager = resource_manager or ResourceManager()
        self.checkpoint_store = checkpoint_store
        self.retry_backoff_seconds = max(0.0, retry_backoff_seconds)

    def run(
        self,
        context: PipelineContext,
        plan: DagPipelinePlan,
        *,
        resume_manifest: CheckpointManifest | None = None,
    ) -> PipelineResult:
        plan.validate()
        completed: set[str] = set()
        pending = list(plan.stages)
        while pending:
            ready = [stage for stage in pending if set(stage.depends_on) <= completed]
            if not ready:
                raise ValueError("DAG could not make progress")
            for spec in ready:
                if self._can_resume(spec, resume_manifest, context):
                    completed.add(spec.name)
                    pending.remove(spec)
                    continue
                stage = self.registry.get(spec.name)
                entry, started_at = context.provenance.start_stage(
                    spec.name, input_summary={"artifact_count": len(context.artifacts)}
                )
                try:
                    context = self._run_with_retry(stage, spec, context)
                except PipelineValidationError as exc:
                    context.provenance.finish_stage(
                        entry, started_at,
                        output_summary={"artifact_count": len(context.artifacts)},
                        errors=[issue.message for issue in exc.issues],
                    )
                    return PipelineResult(context=context, succeeded=False, issues=exc.issues)
                except Exception as exc:
                    issue = ValidationIssue(
                        code="stage_failed", severity="error", message=str(exc), stage=spec.name
                    )
                    context.provenance.finish_stage(
                        entry, started_at,
                        output_summary={"artifact_count": len(context.artifacts)},
                        errors=[issue.message],
                    )
                    return PipelineResult(context=context, succeeded=False, issues=[issue])
                context.provenance.finish_stage(
                    entry, started_at, output_summary={"artifact_count": len(context.artifacts)}
                )
                completed.add(spec.name)
                pending.remove(spec)
                self._save_checkpoint(context, completed)
        return PipelineResult(context=context, succeeded=True)

    def _run_with_retry(self, stage: Any, spec: DagStage, context: PipelineContext) -> PipelineContext:
        attempts = max(0, spec.max_retries) + 1
        for attempt in range(attempts):
            try:
                with self.resource_manager.acquire(spec.resource):
                    return stage.run(context)
            except PipelineValidationError:
                raise
            except Exception:
                if attempt + 1 >= attempts:
                    raise
                if self.retry_backoff_seconds:
                    sleep(self.retry_backoff_seconds * (attempt + 1))
        raise RuntimeError("unreachable")

    @staticmethod
    def _can_resume(
        spec: DagStage,
        manifest: CheckpointManifest | None,
        context: PipelineContext,
    ) -> bool:
        if manifest is None or spec.name not in manifest.completed_stages:
            return False
        # A manifest alone is not enough: the caller must hydrate artifacts first.
        return bool(manifest.artifact_keys) and set(manifest.artifact_keys) <= set(context.artifacts)

    def _save_checkpoint(self, context: PipelineContext, completed: set[str]) -> None:
        if self.checkpoint_store is None:
            return
        self.checkpoint_store.save(
            CheckpointManifest(
                run_id=context.provenance.run_id,
                page_id=context.page_id,
                completed_stages=sorted(completed),
                artifact_keys=sorted(context.artifacts),
            )
        )
