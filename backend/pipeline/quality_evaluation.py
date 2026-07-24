"""Repository-safe quality metrics for licensed or synthetic evaluation corpora."""

from __future__ import annotations

import re
from typing import Any, Iterable

import numpy as np

from ..engines.detection.evaluation import DetectionCase, evaluate_detection_cases


def _edit_distance(left: list[str], right: list[str]) -> int:
    row = list(range(len(right) + 1))
    for i, left_value in enumerate(left, 1):
        next_row = [i]
        for j, right_value in enumerate(right, 1):
            next_row.append(min(
                next_row[-1] + 1,
                row[j] + 1,
                row[j - 1] + (left_value != right_value),
            ))
        row = next_row
    return row[-1]


def character_error_rate(expected: str, predicted: str) -> float:
    left = list(re.sub(r"\s+", "", expected or ""))
    right = list(re.sub(r"\s+", "", predicted or ""))
    return round(_edit_distance(left, right) / max(1, len(left)), 4)


def word_error_rate(expected: str, predicted: str) -> float:
    left = (expected or "").split()
    right = (predicted or "").split()
    return round(_edit_distance(left, right) / max(1, len(left)), 4)


def inpainting_outside_change_ratio(before: np.ndarray, after: np.ndarray, mask: np.ndarray) -> float:
    """Fraction of changed pixels outside the requested inpainting mask."""
    if before.shape != after.shape or before.shape[:2] != mask.shape[:2]:
        raise ValueError("before, after, and mask dimensions do not match")
    changed = np.any(before != after, axis=2) if before.ndim == 3 else before != after
    outside = np.asarray(mask) == 0
    return round(float(np.count_nonzero(changed & outside) / max(1, np.count_nonzero(outside))), 4)


def evaluate_quality_corpus(corpus: dict[str, Any]) -> dict[str, Any]:
    """Evaluate fields present in a corpus without inventing missing metrics.

    Detection cases use ``expected_boxes``/``predicted_boxes``. Text cases use
    ``expected_text``/``predicted_text``. Stage quality records may provide
    ``inpainting_outside_change_ratio`` or ``layout_overflow`` from a real run.
    """
    cases = corpus.get("cases", [])
    detection_cases = [DetectionCase.from_mapping(item) for item in cases if "expected_boxes" in item or "predicted_boxes" in item]
    text_cases = [item for item in cases if "expected_text" in item and "predicted_text" in item]
    stage_cases = [item for item in cases if "inpainting_outside_change_ratio" in item or "layout_overflow" in item]
    result: dict[str, Any] = {"schema_version": 1, "case_count": len(cases), "available": {}}
    if detection_cases:
        result["detection"] = evaluate_detection_cases(detection_cases).as_dict()
        result["available"]["detection"] = True
    if text_cases:
        result["ocr"] = {
            "sample_count": len(text_cases),
            "cer": round(sum(character_error_rate(x["expected_text"], x["predicted_text"]) for x in text_cases) / len(text_cases), 4),
            "wer": round(sum(word_error_rate(x["expected_text"], x["predicted_text"]) for x in text_cases) / len(text_cases), 4),
        }
        result["translation"] = {
            "sample_count": len(text_cases),
            "exact_match_rate": round(sum((x["expected_text"] or "").strip() == (x["predicted_text"] or "").strip() for x in text_cases) / len(text_cases), 4),
        }
        result["available"].update({"ocr": True, "translation": True})
    if stage_cases:
        inpainting = [float(x["inpainting_outside_change_ratio"]) for x in stage_cases if "inpainting_outside_change_ratio" in x]
        overflow = [bool(x["layout_overflow"]) for x in stage_cases if "layout_overflow" in x]
        result["inpainting"] = {"sample_count": len(inpainting), "outside_change_ratio": round(sum(inpainting) / len(inpainting), 4)} if inpainting else {"sample_count": 0}
        result["layout"] = {"sample_count": len(overflow), "overflow_rate": round(sum(overflow) / len(overflow), 4)} if overflow else {"sample_count": 0}
        result["available"].update({"inpainting": bool(inpainting), "layout": bool(overflow)})
    return result
