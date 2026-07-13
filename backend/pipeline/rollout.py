from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable


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


class PipelineExecutionCoordinator:
    """Run a selected pipeline and optionally a non-mutating shadow pipeline."""

    def __init__(
        self,
        *,
        v1_runner: Callable[[Any], Any],
        v2_runner: Callable[[Any], Any] | None = None,
    ) -> None:
        self._runners = {PipelineVariant.V1: v1_runner}
        if v2_runner is not None:
            self._runners[PipelineVariant.V2] = v2_runner
        self.last_comparison: PipelineComparison | None = None

    def run(self, context: Any, rollout: PipelineRollout) -> Any:
        primary_variant = rollout.primary
        primary_runner = self._runners.get(primary_variant)
        if primary_runner is None:
            raise RuntimeError(f"Pipeline {primary_variant.value} is not available")

        primary_result = primary_runner(context)
        shadow_variant = rollout.shadow_variant
        self.last_comparison = None
        if shadow_variant is not None and shadow_variant in self._runners:
            shadow_result = self._run_shadow(context, shadow_variant)
            self.last_comparison = self._compare(
                primary_variant, primary_result, shadow_variant, shadow_result
            )
        return primary_result

    def _run_shadow(self, context: Any, variant: PipelineVariant) -> Any:
        return self._runners[variant](deepcopy(context))

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
