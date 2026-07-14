from __future__ import annotations

from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from time import perf_counter, sleep

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
    parallel_safe: bool = False


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
    """Resource-aware DAG executor with opt-in parallel stage batches."""

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
        self._hydrate_resume_artifacts(context, resume_manifest)
        completed: set[str] = set()
        pending = list(plan.stages)
        while pending:
            ready = [stage for stage in pending if set(stage.depends_on) <= completed]
            if not ready:
                raise ValueError("DAG could not make progress")
            executable = []
            for spec in ready:
                if self._can_resume(spec, resume_manifest, context):
                    completed.add(spec.name)
                    pending.remove(spec)
                    continue
                executable.append(spec)
            if len(executable) > 1 and all(spec.parallel_safe for spec in executable):
                failure = self._run_parallel_batch(context, executable, completed, pending)
                if failure is not None:
                    return failure
                self._save_checkpoint(context, completed)
                continue
            for spec in executable:
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

    def _run_parallel_batch(
        self,
        context: PipelineContext,
        specs: list[DagStage],
        completed: set[str],
        pending: list[DagStage],
    ) -> PipelineResult | None:
        records = {}
        with ThreadPoolExecutor(max_workers=len(specs), thread_name_prefix="pipeline-stage") as pool:
            for spec in specs:
                stage = self.registry.get(spec.name)
                entry, started_at = context.provenance.start_stage(
                    spec.name, input_summary={"artifact_count": len(context.artifacts)}
                )
                records[pool.submit(self._run_parallel_timed, stage, spec, context)] = (
                    spec, entry, started_at
                )
            issues: list[ValidationIssue] = []
            for future, (spec, entry, started_at) in records.items():
                result_context, finished_at, error = future.result()
                try:
                    if error is not None:
                        raise error
                    if result_context is not context:
                        raise RuntimeError("Parallel stages must mutate and return their input context")
                except PipelineValidationError as exc:
                    stage_issues = exc.issues
                    issues.extend(stage_issues)
                except Exception as exc:
                    stage_issues = [ValidationIssue(
                        code="stage_failed", severity="error", message=str(exc), stage=spec.name
                    )]
                    issues.extend(stage_issues)
                else:
                    stage_issues = []
                    completed.add(spec.name)
                    pending.remove(spec)
                context.provenance.finish_stage(
                    entry,
                    started_at,
                    output_summary={"artifact_count": len(context.artifacts)},
                    errors=[issue.message for issue in stage_issues],
                )
                entry.duration_ms = int((finished_at - started_at) * 1000)
        if issues:
            return PipelineResult(context=context, succeeded=False, issues=issues)
        return None

    def _run_parallel_timed(
        self,
        stage: Any,
        spec: DagStage,
        context: PipelineContext,
    ) -> tuple[PipelineContext | None, float, Exception | None]:
        try:
            return self._run_with_retry(stage, spec, context), perf_counter(), None
        except Exception as exc:
            return None, perf_counter(), exc

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
        artifacts = self._checkpoint_artifacts(context)
        self.checkpoint_store.save(
            CheckpointManifest(
                run_id=context.provenance.run_id,
                page_id=context.page_id,
                completed_stages=sorted(completed),
                artifact_keys=sorted(artifacts),
                metadata={
                    "schema_version": 1,
                    "quality_replans": context.artifacts.get("quality_replans", []),
                    "quality_scores": context.artifacts.get("quality_scores", {}),
                },
            )
        )
        save_artifacts = getattr(self.checkpoint_store, "save_artifacts", None)
        if callable(save_artifacts):
            save_artifacts(context.provenance.run_id, artifacts)

    @staticmethod
    def _checkpoint_artifacts(context: PipelineContext) -> dict[str, Any]:
        ephemeral = {"state", "job", "job_manager", "config", "show_progress"}
        return {
            key: value for key, value in context.artifacts.items()
            if key not in ephemeral
        }

    def _hydrate_resume_artifacts(
        self, context: PipelineContext, manifest: CheckpointManifest | None
    ) -> None:
        if manifest is None:
            return
        if manifest.page_id != context.page_id:
            raise ValueError(
                f"Checkpoint page mismatch: expected {context.page_id!r}, got {manifest.page_id!r}"
            )
        load_artifacts = getattr(self.checkpoint_store, "load_artifacts", None)
        if callable(load_artifacts):
            context.artifacts.update(load_artifacts(manifest.run_id))
