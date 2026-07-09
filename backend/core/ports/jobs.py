from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from ..models.jobs import JobStatus


class JobManagerPort(Protocol):
    def submit(self, worker: Callable[[], Any]) -> JobStatus:
        ...

    def get(self, job_id: str) -> JobStatus:
        ...