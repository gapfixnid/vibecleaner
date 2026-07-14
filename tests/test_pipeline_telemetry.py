from types import SimpleNamespace

from backend.pipeline.rollout import PipelineExecutionCoordinator, PipelineRollout
from backend.pipeline.telemetry import JsonlTelemetrySink, load_telemetry, summarize_telemetry


def test_telemetry_sink_round_trips_and_summarizes_fallbacks(tmp_path):
    sink = JsonlTelemetrySink(tmp_path / "telemetry.jsonl")
    coordinator = PipelineExecutionCoordinator(
        v1_runner=lambda context: SimpleNamespace(succeeded=True),
        v2_runner=lambda context: SimpleNamespace(succeeded=False, issues=["v2 failed"]),
        telemetry_sink=sink,
        fallback_context_factory=lambda context: context,
    )
    result = coordinator.run(SimpleNamespace(page_id="page-1"), PipelineRollout(enabled=True))
    assert result.succeeded is True
    records = load_telemetry(tmp_path / "telemetry.jsonl")
    summary = summarize_telemetry(records)
    assert summary["fallback_attempt_count"] == 1
    assert summary["fallback_success_count"] == 1
    assert summary["fallback_attempt_rate"] == 1.0


def test_telemetry_summary_tracks_primary_success_without_fallback(tmp_path):
    sink = JsonlTelemetrySink(tmp_path / "telemetry.jsonl")
    coordinator = PipelineExecutionCoordinator(
        v1_runner=lambda context: SimpleNamespace(succeeded=True),
        v2_runner=lambda context: SimpleNamespace(succeeded=True),
        telemetry_sink=sink,
    )
    coordinator.run(SimpleNamespace(page_id="page-2"), PipelineRollout(enabled=True))
    summary = summarize_telemetry(load_telemetry(tmp_path / "telemetry.jsonl"))
    assert summary["v2_sample_count"] == 1
    assert summary["primary_failure_rate"] == 0.0
    assert summary["fallback_attempt_count"] == 0
