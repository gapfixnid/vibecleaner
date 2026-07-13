from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class QualityScore:
    stage: str
    score: float
    passed: bool
    signals: dict[str, float] = field(default_factory=dict)
    recommended_action: str = "accept"


@dataclass(frozen=True)
class QualityThresholds:
    detection: float = 0.75
    ocr: float = 0.80


class AdaptiveQualityRouter:
    """Convert stage outputs into bounded quality decisions and model upgrades."""

    def __init__(self, thresholds: QualityThresholds | None = None) -> None:
        self.thresholds = thresholds or QualityThresholds()

    def evaluate_detection(self, regions: list[Any]) -> QualityScore:
        confidences = [
            float(value)
            for region in regions
            if (value := getattr(region, "confidence", None)) is not None
        ]
        if not confidences:
            return QualityScore(
                stage="detection",
                score=1.0,
                passed=True,
                signals={"confidence_available": 0.0, "region_count": float(len(regions))},
            )
        mean_confidence = sum(confidences) / len(confidences)
        score = max(0.0, min(1.0, mean_confidence))
        passed = score >= self.thresholds.detection
        return QualityScore(
            stage="detection",
            score=round(score, 4),
            passed=passed,
            signals={"mean_confidence": round(score, 4), "region_count": float(len(regions))},
            recommended_action="accept" if passed else "upgrade_model",
        )

    def evaluate_ocr(self, blocks: list[Any]) -> QualityScore:
        if not blocks:
            return QualityScore("ocr", 1.0, True, {"non_empty_ratio": 1.0})
        non_empty = sum(bool(str(getattr(block, "text", "")).strip()) for block in blocks)
        ratio = non_empty / len(blocks)
        passed = ratio >= self.thresholds.ocr
        return QualityScore(
            stage="ocr",
            score=round(ratio, 4),
            passed=passed,
            signals={"non_empty_ratio": round(ratio, 4), "block_count": float(len(blocks))},
            recommended_action="accept" if passed else "retry_ocr",
        )

    def detection_model_for(self, current_model: str, score: QualityScore) -> str:
        if score.passed:
            return current_model
        return "High Precision (FP32)"
