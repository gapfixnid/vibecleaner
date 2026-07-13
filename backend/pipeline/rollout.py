from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable

from .benchmark import ShadowBenchmarkRecord


class PipelineVariant(StrEnum):
    V1 = "v1"
    V2 = "v2"


@dataclass(frozen=True)
class PipelineRollout:
    """Resolve rollout flags without coupling the domain to API or UI layers."""

    enabled: bool = False
    shadow: bool = False

    @classmethod
    def from_settings(cls, settings: Any) -> "PipelineRollout":
        return cls(
            enabled=bool(getattr(settings, "pipeline_v2_enabled", False)),
            shadow=bool(getattr(settings, "pipeline_v2_shadow", False)),
        )

    @property
    def primary(self) -> PipelineVariant:
        return PipelineVariant.V2 if self.enabled else PipelineVariant.V1

    @property
    def shadow_variant(self) -> PipelineVariant | None:
        if not self.shadow:
            return None
        return PipelineVariant.V1 if self.enabled else PipelineVariant.V2


@dataclass(frozen=True)
class PipelineComparison:
    primary: PipelineVariant
    shadow: PipelineVariant
    primary_succeeded: bool
    shadow_succeeded: bool
    matching_artifact_keys: bool
    primary_error: str | None = None
    shadow_error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def equivalent(self) -> bool:
        return (
            self.primary_succeeded
            and self.shadow_succeeded
            and self.matching_artifact_keys
        )


@dataclass(frozen=True)
class ShadowExecutionFailure:
    succeeded: bool = False
    issues: list[Any] = field(default_factory=list)


class PipelineExecutionCoordinator:
    """Run a selected pipeline and optionally a non-mutating shadow pipeline."""

    def __init__(
        self,
        *,
        v1_runner: Callable[[Any], Any],
        v2_runner: Callable[[Any], Any] | None = None,
        benchmark_sink: Any | None = None,
        shadow_context_factory: Callable[[Any], Any] = deepcopy,
    ) -> None:
        self._runners = {PipelineVariant.V1: v1_runner}
        if v2_runner is not None:
            self._runners[PipelineVariant.V2] = v2_runner
        self.last_comparison: PipelineComparison | None = None
        self.benchmark_sink = benchmark_sink
        self.shadow_context_factory = shadow_context_factory

    def run(self, context: Any, rollout: PipelineRollout) -> Any:
        primary_variant = rollout.primary
        primary_runner = self._runners.get(primary_variant)
        if primary_runner is None:
            raise RuntimeError(f"Pipeline {primary_variant.value} is not available")

        shadow_variant = rollout.shadow_variant
        shadow_context = None
        shadow_copy_error: Exception | None = None
        if shadow_variant is not None and shadow_variant in self._runners:
            try:
                shadow_context = self.shadow_context_factory(context)
            except Exception as exc:
                shadow_copy_error = exc

        primary_result = primary_runner(context)
        self.last_comparison = None
        if shadow_variant is not None and shadow_variant in self._runners:
            try:
                if shadow_copy_error is not None:
                    raise shadow_copy_error
                shadow_result = self._runners[shadow_variant](shadow_context)
            except Exception as exc:
                shadow_result = ShadowExecutionFailure(
                    issues=[f"shadow execution skipped: {exc}"]
                )
            self.last_comparison = self._compare(
                primary_variant, primary_result, shadow_variant, shadow_result
            )
            self._record_benchmark(context, self.last_comparison)
        return primary_result

    def _record_benchmark(self, context: Any, comparison: PipelineComparison) -> None:
        if self.benchmark_sink is None:
            return
        provenance = getattr(context, "provenance", None)
        self.benchmark_sink.record(
            ShadowBenchmarkRecord(
                run_id=str(getattr(provenance, "run_id", "unknown")),
                page_id=str(getattr(context, "page_id", "unknown")),
                primary=comparison.primary.value,
                shadow=comparison.shadow.value,
                equivalent=comparison.equivalent,
                primary_succeeded=comparison.primary_succeeded,
                shadow_succeeded=comparison.shadow_succeeded,
                matching_artifact_keys=comparison.matching_artifact_keys,
                metadata=comparison.metadata,
            )
        )

    @staticmethod
    def _compare(
        primary_variant: PipelineVariant,
        primary_result: Any,
        shadow_variant: PipelineVariant,
        shadow_result: Any,
    ) -> PipelineComparison:
        primary_ok = bool(getattr(primary_result, "succeeded", True))
        shadow_ok = bool(getattr(shadow_result, "succeeded", True))
        primary_context = getattr(primary_result, "context", primary_result)
        shadow_context = getattr(shadow_result, "context", shadow_result)
        primary_artifacts = getattr(primary_context, "artifacts", {})
        shadow_artifacts = getattr(shadow_context, "artifacts", {})
        return PipelineComparison(
            primary=primary_variant,
            shadow=shadow_variant,
            primary_succeeded=primary_ok,
            shadow_succeeded=shadow_ok,
            matching_artifact_keys=set(primary_artifacts) == set(shadow_artifacts),
            primary_error=_error_message(primary_result),
            shadow_error=_error_message(shadow_result),
        )


def _error_message(result: Any) -> str | None:
    issues = getattr(result, "issues", None) or []
    return str(getattr(issues[0], "message", issues[0])) if issues else None
