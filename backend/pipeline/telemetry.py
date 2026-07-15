from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TELEMETRY_SCHEMA_VERSION = 2
DEFAULT_TELEMETRY_FILENAME = "pipeline_telemetry.jsonl"
DEFAULT_TELEMETRY_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_TELEMETRY_RETENTION_DAYS = 30
logger = logging.getLogger(__name__)


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
    def __init__(
        self,
        path: str | Path,
        *,
        max_bytes: int = DEFAULT_TELEMETRY_MAX_BYTES,
        retention_days: int = DEFAULT_TELEMETRY_RETENTION_DAYS,
    ) -> None:
        self.path = Path(path)
        self.max_bytes = max(1024, int(max_bytes))
        self.retention_days = max(1, int(retention_days))

    def record(self, record: PipelineTelemetryRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
        self._prune()

    def _prune(self) -> None:
        if not self.path.exists():
            return
        cutoff = datetime.now(timezone.utc).timestamp() - self.retention_days * 86400
        retained: list[str] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                recorded_at = datetime.fromisoformat(
                    str(row.get("recorded_at", "")).replace("Z", "+00:00")
                ).timestamp()
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
            if recorded_at >= cutoff:
                retained.append(json.dumps(row, ensure_ascii=False))
        while retained and len(("\n".join(retained) + "\n").encode("utf-8")) > self.max_bytes:
            retained.pop(0)
        self.path.write_text(("\n".join(retained) + "\n") if retained else "", encoding="utf-8")


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
            logger.warning("Skipping invalid telemetry JSONL at line %d: %s", line_number, exc)
    return records


def summarize_telemetry(records: list[dict[str, Any]]) -> dict[str, Any]:
    def mean(values: list[Any]) -> float | None:
        numbers = [float(value) for value in values if value is not None]
        return round(sum(numbers) / len(numbers), 4) if numbers else None

    def summarize_group(group: list[dict[str, Any]]) -> dict[str, Any]:
        stage_durations: dict[str, list[float]] = defaultdict(list)
        stage_retries: dict[str, list[int]] = defaultdict(list)
        stage_cache_hits: dict[str, list[int]] = defaultdict(list)
        stage_cache_misses: dict[str, list[int]] = defaultdict(list)
        quality_values: dict[str, list[float]] = defaultdict(list)
        quality_passes: dict[str, list[bool]] = defaultdict(list)
        for row in group:
            for stage, details in (row.get("stages") or {}).items():
                if details.get("duration_ms") is not None:
                    stage_durations[stage].append(float(details["duration_ms"]))
                if details.get("retry_count") is not None:
                    stage_retries[stage].append(int(details["retry_count"]))
                if details.get("cache_hits") is not None:
                    stage_cache_hits[stage].append(int(details["cache_hits"]))
                if details.get("cache_misses") is not None:
                    stage_cache_misses[stage].append(int(details["cache_misses"]))
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
            "stage_retry_count": {
                stage: sum(values) for stage, values in sorted(stage_retries.items())
            },
            "stage_cache_hits": {
                stage: sum(values) for stage, values in sorted(stage_cache_hits.items())
            },
            "stage_cache_misses": {
                stage: sum(values) for stage, values in sorted(stage_cache_misses.items())
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
