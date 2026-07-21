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
    inpainting: float = 0.70
    inpainting_min_target_change: float = 0.02
    inpainting_min_outside_preserved: float = 0.97
    ocr_by_language: dict[str, float] = field(default_factory=lambda: {
        "Japanese": 0.80,
        "English": 0.75,
        "Korean": 0.78,
    })

    def ocr_threshold(self, language: str | None = None) -> float:
        if not language:
            return self.ocr
        normalized = str(language).strip().lower()
        aliases = {
            "japanese": "Japanese", "日本語": "Japanese", "ja": "Japanese",
            "english": "English", "영어": "English", "en": "English",
            "korean": "Korean", "한국어": "Korean", "ko": "Korean",
        }
        return self.ocr_by_language.get(aliases.get(normalized, str(language)), self.ocr)


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

    def evaluate_ocr(self, blocks: list[Any], language: str | None = None) -> QualityScore:
        threshold = self.thresholds.ocr_threshold(language)
        if not blocks:
            return QualityScore("ocr", 1.0, True, {"non_empty_ratio": 1.0, "threshold": threshold})
        non_empty = sum(bool(str(getattr(block, "text", "")).strip()) for block in blocks)
        ratio = non_empty / len(blocks)
        raw_confidences = [
            float(value) for block in blocks
            if (value := getattr(block, "ocr_confidence", None)) is not None
        ]
        passed = ratio >= threshold
        signals = {
            "non_empty_ratio": round(ratio, 4),
            "block_count": float(len(blocks)),
            "threshold": threshold,
            "raw_confidence_available_ratio": round(len(raw_confidences) / len(blocks), 4),
        }
        if raw_confidences:
            signals["raw_confidence_mean"] = round(sum(raw_confidences) / len(raw_confidences), 4)
        return QualityScore(
            stage="ocr",
            score=round(ratio, 4),
            passed=passed,
            signals=signals,
            recommended_action="accept" if passed else "retry_ocr",
        )

    def evaluate_inpainting(self, original: Any, result: Any, boxes: list[Any]) -> QualityScore:
        """Score output validity, target change, and preservation outside masks."""
        try:
            if result is None or getattr(result, "shape", None) != getattr(original, "shape", None):
                return QualityScore("inpainting", 0.0, False, {"valid_output": 0.0}, "retry_inpainting")
            if getattr(result, "dtype", None) != getattr(original, "dtype", None) or not bool(getattr(result, "size", 0)):
                return QualityScore("inpainting", 0.0, False, {"valid_output": 0.0}, "retry_inpainting")
            import numpy as np
            mask = np.zeros(original.shape[:2], dtype=bool)
            height, width = mask.shape
            for box in boxes:
                x1, y1, x2, y2 = [int(value) for value in box]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(width, x2), min(height, y2)
                if x2 > x1 and y2 > y1:
                    mask[y1:y2, x1:x2] = True
            if not mask.any():
                return QualityScore("inpainting", 1.0, True, {"target_area": 0.0})
            diff = np.mean(np.abs(result.astype(np.float32) - original.astype(np.float32)), axis=2)
            target_change = float(np.mean(diff[mask] > 1.0))
            outside = ~mask
            outside_preserved = 1.0
            if outside.any() and float(np.std(original.astype(np.float32)[outside])) > 1.0:
                outside_preserved = float(np.mean(diff[outside] <= 2.0))
            # Only text strokes should change inside a rectangular text box;
            # requiring most pixels in the box to change incorrectly rejects
            # clean results dominated by whitespace. Normalize modest target
            # change while independently enforcing outside preservation.
            normalized_target_change = min(1.0, target_change / 0.15)
            score = min(1.0, 0.7 * normalized_target_change + 0.3 * outside_preserved)
            passed = (
                score >= self.thresholds.inpainting
                and target_change >= self.thresholds.inpainting_min_target_change
                and outside_preserved >= self.thresholds.inpainting_min_outside_preserved
            )
            return QualityScore(
                "inpainting", round(score, 4), passed,
                {"target_change_ratio": round(target_change, 4), "outside_preserved_ratio": round(outside_preserved, 4)},
                "accept" if passed else "retry_inpainting",
            )
        except Exception:
            return QualityScore("inpainting", 0.0, False, {"valid_output": 0.0}, "retry_inpainting")

    def detection_model_for(self, current_model: str, score: QualityScore) -> str:
        return self.select_model("detection", current_model, score)

    def select_model(
        self,
        stage: str,
        current_model: str,
        score: QualityScore,
        provider_manifest: Any | None = None,
        *,
        available_resources: set[str] | frozenset[str] | None = None,
    ) -> str:
        """Select a catalog profile after a quality decision.

        Passing quality keeps the configured model. A failed score selects the
        highest-quality compatible alternative, preferring a profile that is
        not the current one. Resource filtering prevents a replan from
        selecting a model unavailable to the runtime.
        """
        if score.passed:
            return current_model
        profiles = tuple(getattr(provider_manifest, "model_catalog", ()) or ())
        if not profiles:
            defaults = {
                "detection": ("High Precision (FP32)",),
                "ocr": ("balanced",),
                "inpainting": ("opencv",),
            }
            return next((value for value in defaults.get(stage, ()) if value != current_model), current_model)
        resources = frozenset(available_resources or {"cpu", "gpu", "io", "network"})
        compatible = [
            profile for profile in profiles
            if profile.resource_classes.issubset(resources)
        ]
        current_profile = next(
            (profile for profile in compatible if profile.selection_value == current_model),
            None,
        )
        if current_profile is None:
            candidates = compatible
        else:
            # A quality retry must be an actual upgrade. Selecting a faster but
            # lower-quality alternative after a failed quality check both wastes
            # time and can replace a better result with a worse one.
            candidates = [
                profile for profile in compatible
                if profile.selection_value != current_model
                and profile.quality_score > current_profile.quality_score
            ]
        if not candidates:
            return current_model
        return max(candidates, key=lambda profile: (profile.quality_score, profile.latency_score)).selection_value
