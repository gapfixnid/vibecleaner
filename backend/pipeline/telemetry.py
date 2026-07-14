from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PipelineTelemetryRecord:
    run_id: str
    page_id: str
    primary: str
    primary_succeeded: bool
    returned_variant: str
    fallback_attempted: bool
    fallback_used: bool
    fallback_succeeded: bool | None = None
    shadow_enabled: bool = False
    shadow_succeeded: bool | None = None
    primary_error: str | None = None
    shadow_error: str | None = None
    primary_duration_ms: float | None = None
    shadow_duration_ms: float | None = None
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
    def rate(values: list[Any]) -> float:
        return round(sum(bool(value) for value in values) / len(values), 4) if values else 0.0

    def mean(key: str, values: list[dict[str, Any]]) -> float | None:
        numbers = [float(row[key]) for row in values if row.get(key) is not None]
        return round(sum(numbers) / len(numbers), 4) if numbers else None

    def summarize_group(group: list[dict[str, Any]]) -> dict[str, Any]:
        v2 = [row for row in group if row.get("primary") == "v2"]
        fallback_attempts = [row for row in v2 if row.get("fallback_attempted")]
        fallback_successes = [row for row in fallback_attempts if row.get("fallback_succeeded")]
        return {
            "sample_count": len(group),
            "v2_sample_count": len(v2),
            "primary_failure_rate": round(1 - rate([row.get("primary_succeeded") for row in v2]), 4) if v2 else 0.0,
            "fallback_attempt_rate": round(len(fallback_attempts) / len(v2), 4) if v2 else 0.0,
            "fallback_success_rate": round(len(fallback_successes) / len(fallback_attempts), 4) if fallback_attempts else 0.0,
            "shadow_rate": rate([row.get("shadow_enabled") for row in group]),
            "primary_duration_ms_mean": mean("primary_duration_ms", v2),
            "fallback_attempt_count": len(fallback_attempts),
            "fallback_success_count": len(fallback_successes),
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
        "schema_version": 1,
        **summarize_group(records),
        "by_date": {date: summarize_group(rows) for date, rows in sorted(by_date.items())},
    }
    return result
