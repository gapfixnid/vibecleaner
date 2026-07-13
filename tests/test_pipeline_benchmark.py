import json

from backend.pipeline.benchmark import JsonlBenchmarkSink, ShadowBenchmarkRecord


def test_benchmark_sink_appends_jsonl_record(tmp_path):
    path = tmp_path / "shadow.jsonl"
    sink = JsonlBenchmarkSink(path)
    sink.record(ShadowBenchmarkRecord("run", "page", "v1", "v2", True, True, True, True))
    row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert row["run_id"] == "run"
    assert row["equivalent"] is True
