from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class BubbleProblemCode(str, Enum):
    BUBBLE_ASSOCIATION_UNCERTAIN = "BUBBLE_ASSOCIATION_UNCERTAIN"
    MASK_UNCERTAIN = "MASK_UNCERTAIN"
    OCR_UNCERTAIN = "OCR_UNCERTAIN"
    TRANSLATION_EXPANDED = "TRANSLATION_EXPANDED"
    TEXT_OVERFLOW = "TEXT_OVERFLOW"
    LEGACY_REVIEW_NOTE = "LEGACY_REVIEW_NOTE"


@dataclass(frozen=True, eq=False)
class BubbleProblem:
    code: BubbleProblemCode
    detail: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {"code": self.code.value, "detail": self.detail}

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BubbleProblem):
            return self.code == other.code and self.detail == other.detail
        if isinstance(other, str):
            return self.detail == other or self.code.value == other
        return False

    def __hash__(self) -> int:
        return hash((self.code, self.detail))


def normalize_bubble_problem(value: Any) -> BubbleProblem:
    if isinstance(value, BubbleProblem):
        return value
    if isinstance(value, dict):
        raw_code = str(value.get("code", "") or "")
        try:
            code = BubbleProblemCode(raw_code)
        except ValueError:
            return BubbleProblem(
                BubbleProblemCode.LEGACY_REVIEW_NOTE,
                str(value.get("detail") or raw_code or value),
            )
        detail = value.get("detail")
        return BubbleProblem(
            code,
            str(detail) if detail is not None else None,
        )

    detail = str(value)
    normalized = detail.strip()
    known_legacy = {
        "layout overflow": BubbleProblemCode.TEXT_OVERFLOW,
        "text overflow": BubbleProblemCode.TEXT_OVERFLOW,
        "TEXT_OVERFLOW": BubbleProblemCode.TEXT_OVERFLOW,
        "OCR_UNCERTAIN": BubbleProblemCode.OCR_UNCERTAIN,
        "MASK_UNCERTAIN": BubbleProblemCode.MASK_UNCERTAIN,
        "BUBBLE_ASSOCIATION_UNCERTAIN": (
            BubbleProblemCode.BUBBLE_ASSOCIATION_UNCERTAIN
        ),
        "TRANSLATION_EXPANDED": (
            BubbleProblemCode.TRANSLATION_EXPANDED
        ),
    }
    code = known_legacy.get(normalized)
    if code is None:
        code = known_legacy.get(normalized.lower())
    if code is not None:
        return BubbleProblem(code)
    return BubbleProblem(
        BubbleProblemCode.LEGACY_REVIEW_NOTE,
        detail,
    )


DERIVED_PROBLEM_CODES = {
    BubbleProblemCode.BUBBLE_ASSOCIATION_UNCERTAIN,
    BubbleProblemCode.MASK_UNCERTAIN,
    BubbleProblemCode.OCR_UNCERTAIN,
    BubbleProblemCode.TRANSLATION_EXPANDED,
    BubbleProblemCode.TEXT_OVERFLOW,
}


# These signals can only be replaced by redetection/re-OCR/body-mask analysis.
# Layout-only refreshes must retain them after loading a project.
PERSISTED_INPUT_SIGNAL_CODES = {
    BubbleProblemCode.BUBBLE_ASSOCIATION_UNCERTAIN,
    BubbleProblemCode.MASK_UNCERTAIN,
    BubbleProblemCode.OCR_UNCERTAIN,
}


def reconcile_bubble_problems(
    existing: list[BubbleProblem],
    *,
    derived: set[BubbleProblemCode],
) -> list[BubbleProblem]:
    normalized = [
        normalize_bubble_problem(problem) for problem in existing
    ]
    preserved = [
        problem
        for problem in normalized
        if problem.code not in DERIVED_PROBLEM_CODES
    ]
    return preserved + [
        BubbleProblem(code)
        for code in sorted(derived, key=lambda value: value.value)
    ]
