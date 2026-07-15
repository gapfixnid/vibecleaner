"""Detection quality evaluation helpers.

The evaluator is intentionally independent of an image or a model runtime. A
corpus can therefore use licensed annotations, synthetic boxes, or predictions
captured from a real run without making the test suite depend on model files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence


Box = Sequence[float]


def box_iou(left: Box, right: Box) -> float:
    """Return intersection-over-union for two ``x1, y1, x2, y2`` boxes."""
    lx1, ly1, lx2, ly2 = (float(value) for value in left[:4])
    rx1, ry1, rx2, ry2 = (float(value) for value in right[:4])
    intersection_width = max(0.0, min(lx2, rx2) - max(lx1, rx1))
    intersection_height = max(0.0, min(ly2, ry2) - max(ly1, ry1))
    intersection = intersection_width * intersection_height
    left_area = max(0.0, lx2 - lx1) * max(0.0, ly2 - ly1)
    right_area = max(0.0, rx2 - rx1) * max(0.0, ry2 - ry1)
    union = left_area + right_area - intersection
    return intersection / union if union > 0.0 else 0.0


def _as_box(value: Any) -> list[float]:
    coordinates = getattr(value, "xyxy", value)
    if hasattr(coordinates, "tolist"):
        coordinates = coordinates.tolist()
    if not isinstance(coordinates, (list, tuple)) or len(coordinates) < 4:
        raise ValueError(f"Detection box must contain four coordinates: {value!r}")
    return [float(coordinates[index]) for index in range(4)]


@dataclass(frozen=True)
class DetectionCase:
    case_id: str
    expected_boxes: tuple[tuple[float, ...], ...]
    predicted_boxes: tuple[tuple[float, ...], ...]
    category: str = "uncategorized"

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "DetectionCase":
        expected = tuple(tuple(_as_box(box)) for box in value.get("expected_boxes", ()))
        predicted = tuple(tuple(_as_box(box)) for box in value.get("predicted_boxes", ()))
        case_id = str(value.get("case_id") or value.get("id") or "case")
        return cls(
            case_id=case_id,
            category=str(value.get("category") or "uncategorized"),
            expected_boxes=expected,
            predicted_boxes=predicted,
        )


@dataclass(frozen=True)
class DetectionMetrics:
    sample_count: int
    expected_count: int
    predicted_count: int
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float
    f1: float
    split_count: int
    merge_count: int
    by_category: dict[str, dict[str, Any]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "sample_count": self.sample_count,
            "expected_count": self.expected_count,
            "predicted_count": self.predicted_count,
            "true_positive": self.true_positive,
            "false_positive": self.false_positive,
            "false_negative": self.false_negative,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "split_count": self.split_count,
            "merge_count": self.merge_count,
            "by_category": self.by_category,
        }


def _safe_rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _evaluate_group(cases: list[DetectionCase], iou_threshold: float) -> dict[str, Any]:
    expected_count = sum(len(case.expected_boxes) for case in cases)
    predicted_count = sum(len(case.predicted_boxes) for case in cases)
    true_positive = false_positive = false_negative = split_count = merge_count = 0

    for case in cases:
        overlaps = [
            [box_iou(expected, predicted) for predicted in case.predicted_boxes]
            for expected in case.expected_boxes
        ]
        candidates = sorted(
            (
                score,
                expected_index,
                predicted_index,
            )
            for expected_index, row in enumerate(overlaps)
            for predicted_index, score in enumerate(row)
            if score >= iou_threshold
        )
        matched_expected: set[int] = set()
        matched_predicted: set[int] = set()
        for _, expected_index, predicted_index in reversed(candidates):
            if expected_index in matched_expected or predicted_index in matched_predicted:
                continue
            matched_expected.add(expected_index)
            matched_predicted.add(predicted_index)

        true_positive += len(matched_expected)
        false_positive += len(case.predicted_boxes) - len(matched_predicted)
        false_negative += len(case.expected_boxes) - len(matched_expected)
        split_count += sum(
            sum(score >= iou_threshold for score in row) > 1 for row in overlaps
        )
        merge_count += sum(
            sum(overlaps[expected_index][predicted_index] >= iou_threshold for expected_index in range(len(overlaps))) > 1
            for predicted_index in range(len(case.predicted_boxes))
        )

    precision = _safe_rate(true_positive, true_positive + false_positive)
    recall = _safe_rate(true_positive, true_positive + false_negative)
    f1 = _safe_rate(2 * precision * recall, precision + recall)
    return {
        "sample_count": len(cases),
        "expected_count": expected_count,
        "predicted_count": predicted_count,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "split_count": split_count,
        "merge_count": merge_count,
    }


def evaluate_detection_cases(
    cases: Iterable[DetectionCase],
    *,
    iou_threshold: float = 0.5,
) -> DetectionMetrics:
    """Evaluate detection boxes with one-to-one IoU matching.

    ``split_count`` counts one expected region covered by multiple predictions;
    ``merge_count`` counts one prediction covering multiple expected regions.
    These diagnostics are reported separately because both can produce an
    apparently acceptable page-level recall while harming OCR and rendering.
    """
    if not 0.0 < iou_threshold <= 1.0:
        raise ValueError("iou_threshold must be greater than 0 and at most 1")
    case_list = list(cases)
    overall = _evaluate_group(case_list, iou_threshold)
    categories: dict[str, list[DetectionCase]] = {}
    for case in case_list:
        categories.setdefault(case.category, []).append(case)
    by_category = {
        category: _evaluate_group(group, iou_threshold)
        for category, group in sorted(categories.items())
    }
    return DetectionMetrics(**overall, by_category=by_category)
