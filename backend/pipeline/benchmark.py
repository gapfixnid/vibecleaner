from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ShadowBenchmarkRecord:
    run_id: str
    page_id: str
    primary: str
    shadow: str
    equivalent: bool
    primary_succeeded: bool
    shadow_succeeded: bool
    matching_artifact_keys: bool
    primary_duration_ms: float | None = None
    shadow_duration_ms: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    recorded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class JsonlBenchmarkSink:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def record(self, record: ShadowBenchmarkRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

