from dataclasses import dataclass, field
from types import SimpleNamespace

from backend.pipeline.rollout import (
    PipelineExecutionCoordinator,
    PipelineRollout,
    PipelineVariant,
)


@dataclass
class Settings:
    pipeline_v2_enabled: bool = False
    pipeline_v2_shadow: bool = False


@dataclass
class Result:
    succeeded: bool = True
    artifacts: dict = field(default_factory=dict)


def test_rollout_defaults_to_v1_and_can_select_v2():
    assert PipelineRollout.from_settings(Settings()).primary is PipelineVariant.V1
    rollout = PipelineRollout.from_settings(Settings(True, False))
    assert rollout.primary is PipelineVariant.V2
    assert rollout.shadow_variant is None


def test_shadow_runs_on_copy_and_does_not_mutate_primary_context():
    calls = []

    def v1(context):
        calls.append(("v1", context))
        context.artifacts["v1"] = True
        return Result(artifacts=context.artifacts)

    def v2(context):
        calls.append(("v2", context))
        context.artifacts["v2"] = True
        return Result(artifacts=context.artifacts)

    context = SimpleNamespace(artifacts={"input": 1})
    coordinator = PipelineExecutionCoordinator(v1_runner=v1, v2_runner=v2)
    result = coordinator.run(context, PipelineRollout(shadow=True))

    assert result.artifacts == {"input": 1, "v1": True}
    assert calls[0][0] == "v1"
    assert calls[1][0] == "v2"
    assert calls[0][1] is context
    assert calls[1][1] is not context
    assert coordinator.last_comparison is not None
    assert not coordinator.last_comparison.equivalent


def test_missing_v2_runner_is_not_selected_or_shadowed():
    coordinator = PipelineExecutionCoordinator(v1_runner=lambda context: context)
    context = object()
    assert coordinator.run(context, PipelineRollout(shadow=True)) is context
    assert coordinator.last_comparison is None
