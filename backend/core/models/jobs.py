from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


JobStatusValue = Literal["queued", "running", "succeeded", "failed"]


@dataclass
class JobStatus:
    job_id: str
    status: JobStatusValue
    result: dict[str, Any] | None = None
    error: str | None = None
    progress: float = 0.0
    messages: list[str] = field(default_factory=list)
