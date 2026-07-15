from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TELEMETRY_SCHEMA_VERSION = 2
DEFAULT_TELEMETRY_FILENAME = "pipeline_telemetry.jsonl"


@dataclass(frozen=True)
class PipelineTelemetryRecord:
    schema_version: int
    run_id: str
    page_id: str
    succeeded: bool
    duration_ms: float | None = None
    stages: dict[str, dict[str, Any]] = field(default_factory=dict)
    quality_scores: dict[str, dict[str, Any]] = field(default_factory=dict)
    quality_replans: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    recorded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class JsonlTelemetrySink:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def record(self, record: PipelineTelemetryRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def load_telemetry(path: str | Path) -> list[dict[str, Any]]:
    target = Path(path)
    if not target.exists():
        return []
    records = []
    for line_number, line in enumerate(target.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid telemetry JSONL at line {line_number}: {exc}") from exc
    return records


def summarize_telemetry(records: list[dict[str, Any]]) -> dict[str, Any]:
    def mean(values: list[Any]) -> float | None:
        numbers = [float(value) for value in values if value is not None]
        return round(sum(numbers) / len(numbers), 4) if numbers else None

    def summarize_group(group: list[dict[str, Any]]) -> dict[str, Any]:
        stage_durations: dict[str, list[float]] = defaultdict(list)
        quality_values: dict[str, list[float]] = defaultdict(list)
        quality_passes: dict[str, list[bool]] = defaultdict(list)
        for row in group:
            for stage, details in (row.get("stages") or {}).items():
                if details.get("duration_ms") is not None:
                    stage_durations[stage].append(float(details["duration_ms"]))
            for stage, score in (row.get("quality_scores") or {}).items():
                if score.get("score") is not None:
                    quality_values[stage].append(float(score["score"]))
                if score.get("passed") is not None:
                    quality_passes[stage].append(bool(score["passed"]))
        return {
            "sample_count": len(group),
            "success_rate": round(sum(bool(row.get("succeeded")) for row in group) / len(group), 4) if group else 0.0,
            "failure_count": sum(not bool(row.get("succeeded")) for row in group),
            "duration_ms_mean": mean([row.get("duration_ms") for row in group]),
            "replan_count": sum(len(row.get("quality_replans") or []) for row in group),
            "stage_duration_ms_mean": {
                stage: mean(values) for stage, values in sorted(stage_durations.items())
            },
            "quality_score_mean": {
                stage: mean(values) for stage, values in sorted(quality_values.items())
            },
            "quality_pass_rate": {
                stage: round(sum(values) / len(values), 4) if values else 0.0
                for stage, values in sorted(quality_passes.items())
            },
        }

    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        timestamp = str(row.get("recorded_at", "unknown"))
        try:
            date = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            date = "unknown"
        by_date[date].append(row)

    result = {
        "schema_version": TELEMETRY_SCHEMA_VERSION,
        **summarize_group(records),
        "by_date": {date: summarize_group(rows) for date, rows in sorted(by_date.items())},
    }
    return result
