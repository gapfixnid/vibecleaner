from dataclasses import dataclass, field
from types import SimpleNamespace

from backend.pipeline.benchmark import JsonlBenchmarkSink
from backend.pipeline.rollout import PipelineExecutionCoordinator, PipelineRollout, PipelineVariant


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
        calls.append(("v1", context)); context.artifacts["v1"] = True; return Result(artifacts=context.artifacts)
    def v2(context):
        calls.append(("v2", context)); context.artifacts["v2"] = True; return Result(artifacts=context.artifacts)
    context = SimpleNamespace(artifacts={"input": 1})
    coordinator = PipelineExecutionCoordinator(v1_runner=v1, v2_runner=v2)
    result = coordinator.run(context, PipelineRollout(shadow=True))
    assert result.artifacts == {"input": 1, "v1": True}
    assert calls[1][1] is not context
    assert coordinator.last_comparison is not None


def test_missing_v2_runner_is_not_selected_or_shadowed():
    coordinator = PipelineExecutionCoordinator(v1_runner=lambda context: context)
    context = object()
    assert coordinator.run(context, PipelineRollout(shadow=True)) is context
    assert coordinator.last_comparison is None


def test_shadow_comparison_can_be_recorded(tmp_path):
    context = SimpleNamespace(artifacts={"input": 1}, page_id="page", provenance=SimpleNamespace(run_id="run"))
    sink = JsonlBenchmarkSink(tmp_path / "shadow.jsonl")
    coordinator = PipelineExecutionCoordinator(
        v1_runner=lambda item: Result(artifacts=item.artifacts),
        v2_runner=lambda item: Result(artifacts=item.artifacts),
        benchmark_sink=sink,
    )
    coordinator.run(context, PipelineRollout(shadow=True))
    assert sink.path.exists()


def test_shadow_copy_failure_does_not_fail_primary_result():
    class Uncopyable:
        def __deepcopy__(self, memo):
            raise TypeError("lock")

    context = SimpleNamespace(artifacts={"state": Uncopyable()}, page_id="page")
    coordinator = PipelineExecutionCoordinator(
        v1_runner=lambda item: Result(artifacts=item.artifacts),
        v2_runner=lambda item: Result(artifacts=item.artifacts),
    )
    result = coordinator.run(context, PipelineRollout(shadow=True))
    assert result.succeeded
    assert coordinator.last_comparison is not None
    assert not coordinator.last_comparison.shadow_succeeded
