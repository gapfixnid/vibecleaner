from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: Literal["warning", "error"]
    message: str
    stage: str | None = None
    retryable: bool = False
    details: dict[str, Any] | None = None


class PipelineValidationError(Exception):
    def __init__(self, issues: list[ValidationIssue]) -> None:
        self.issues = issues
        super().__init__("; ".join(issue.message for issue in issues))


class PipelineJobError(RuntimeError):
    """Preserve the first structured pipeline issue at the Job boundary."""

    def __init__(self, issue: ValidationIssue) -> None:
        super().__init__(issue.message)
        self.code = issue.code
        self.stage = issue.stage
        self.retryable = issue.retryable
        self.details = dict(issue.details or {})
