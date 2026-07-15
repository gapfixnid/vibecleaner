from __future__ import annotations

import json

from backend.pipeline.telemetry import (
    TELEMETRY_SCHEMA_VERSION,
    JsonlTelemetrySink,
    PipelineTelemetryRecord,
    load_telemetry,
    summarize_telemetry,
)


def test_v2_telemetry_record_contains_stage_quality_and_error_data(tmp_path):
    path = tmp_path / "pipeline_telemetry.jsonl"
    JsonlTelemetrySink(path).record(
        PipelineTelemetryRecord(
            schema_version=TELEMETRY_SCHEMA_VERSION,
            run_id="run-1",
            page_id="page-1",
            succeeded=False,
            duration_ms=125.5,
            stages={"detection": {"duration_ms": 20, "error_count": 0}},
            quality_scores={"ocr": {"score": 0.5, "passed": False}},
            quality_replans=[{"stage": "ocr", "profile": "enhanced_preprocessing"}],
            errors=["OCR failed"],
        )
    )

    rows = load_telemetry(path)

    assert rows[0]["schema_version"] == 2
    assert rows[0]["stages"]["detection"]["duration_ms"] == 20
    assert rows[0]["quality_scores"]["ocr"]["passed"] is False
    assert rows[0]["errors"] == ["OCR failed"]


def test_telemetry_summary_reports_v2_execution_metrics():
    records = [
        {
            "schema_version": 2,
            "recorded_at": "2026-07-15T00:00:00+00:00",
            "succeeded": True,
            "duration_ms": 100,
            "quality_replans": [],
            "stages": {"ocr": {"duration_ms": 40, "retry_count": 1, "cache_hits": 2, "cache_misses": 3}},
            "quality_scores": {"ocr": {"score": 1.0, "passed": True}},
        },
        {
            "schema_version": 2,
            "recorded_at": "2026-07-15T00:01:00+00:00",
            "succeeded": False,
            "duration_ms": 200,
            "quality_replans": [{"stage": "ocr"}],
            "stages": {"ocr": {"duration_ms": 80, "retry_count": 2, "cache_hits": 4, "cache_misses": 1}},
            "quality_scores": {"ocr": {"score": 0.5, "passed": False}},
        },
    ]

    summary = summarize_telemetry(records)

    assert summary["schema_version"] == TELEMETRY_SCHEMA_VERSION
    assert summary["sample_count"] == 2
    assert summary["success_rate"] == 0.5
    assert summary["failure_count"] == 1
    assert summary["duration_ms_mean"] == 150.0
    assert summary["replan_count"] == 1
    assert summary["stage_duration_ms_mean"]["ocr"] == 60.0
    assert summary["stage_retry_count"]["ocr"] == 3
    assert summary["stage_cache_hits"]["ocr"] == 6
    assert summary["stage_cache_misses"]["ocr"] == 4
    assert summary["quality_score_mean"]["ocr"] == 0.75
    assert summary["quality_pass_rate"]["ocr"] == 0.5
    assert summary["by_date"]["2026-07-15"]["sample_count"] == 2


def test_telemetry_sink_writes_one_json_record_per_line(tmp_path):
    path = tmp_path / "telemetry.jsonl"
    sink = JsonlTelemetrySink(path)
    record = PipelineTelemetryRecord(
        schema_version=2,
        run_id="run-1",
        page_id="page-1",
        succeeded=True,
    )

    sink.record(record)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["run_id"] == "run-1"


def test_corrupt_telemetry_rows_are_skipped(tmp_path):
    path = tmp_path / "telemetry.jsonl"
    path.write_text('{"run_id":"good"}\nnot-json\n', encoding="utf-8")

    assert load_telemetry(path) == [{"run_id": "good"}]


def test_telemetry_sink_prunes_oldest_rows_when_size_limit_is_reached(tmp_path):
    path = tmp_path / "telemetry.jsonl"
    sink = JsonlTelemetrySink(path, max_bytes=1024, retention_days=3650)
    for index in range(20):
        sink.record(PipelineTelemetryRecord(
            schema_version=2, run_id=f"run-{index}", page_id="page", succeeded=True,
            metadata={"padding": "x" * 100},
        ))

    assert path.stat().st_size <= 1024
    rows = load_telemetry(path)
    assert rows
    assert rows[-1]["run_id"] == "run-19"
