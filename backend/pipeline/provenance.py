from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4


@dataclass
class StageProvenance:
    stage: str
    engine: str | None = None
    options: dict[str, object] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: int = 0
    input_summary: dict[str, object] = field(default_factory=dict)
    output_summary: dict[str, object] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class ProvenanceTrace:
    run_id: str = field(default_factory=lambda: str(uuid4()))
    page_id: str | None = None
    stages: list[StageProvenance] = field(default_factory=list)

    def start_stage(self, stage: str, input_summary: dict[str, object] | None = None) -> tuple[StageProvenance, float]:
        entry = StageProvenance(stage=stage, input_summary=input_summary or {})
        self.stages.append(entry)
        return entry, perf_counter()

    def finish_stage(
        self,
        entry: StageProvenance,
        started_at: float,
        *,
        output_summary: dict[str, object] | None = None,
        warnings: list[str] | None = None,
        errors: list[str] | None = None,
    ) -> None:
        entry.duration_ms = int((perf_counter() - started_at) * 1000)
        entry.output_summary = output_summary or {}
        entry.warnings.extend(warnings or [])
        entry.errors.extend(errors or [])
