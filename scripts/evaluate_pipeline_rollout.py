#!/usr/bin/env python3
"""Evaluate shadow benchmark JSONL against Pipeline v2 rollout gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def evaluate_records(
    records: list[dict[str, Any]],
    *,
    minimum_samples: int = 10,
    minimum_success_rate: float = 0.99,
    minimum_equivalence_rate: float = 0.99,
    minimum_text_match: float = 0.99,
) -> dict[str, Any]:
    sample_count = len(records)
    success_count = sum(
        bool(row.get("primary_succeeded")) and bool(row.get("shadow_succeeded"))
        for row in records
    )
    equivalent_count = sum(bool(row.get("equivalent")) for row in records)
    ocr_values = [
        float(row.get("metadata", {}).get("ocr_text_match_ratio"))
        for row in records
        if row.get("metadata", {}).get("ocr_text_match_ratio") is not None
    ]
    translation_values = [
        float(row.get("metadata", {}).get("translation_match_ratio"))
        for row in records
        if row.get("metadata", {}).get("translation_match_ratio") is not None
    ]

    def rate(count: int) -> float:
        return count / sample_count if sample_count else 0.0

    def mean(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    metrics = {
        "sample_count": sample_count,
        "success_rate": round(rate(success_count), 4),
        "equivalence_rate": round(rate(equivalent_count), 4),
        "ocr_text_match_mean": round(mean(ocr_values), 4),
        "translation_match_mean": round(mean(translation_values), 4),
    }
    failures = []
    if sample_count < minimum_samples:
        failures.append(f"requires at least {minimum_samples} samples")
    if metrics["success_rate"] < minimum_success_rate:
        failures.append("success rate below threshold")
    if metrics["equivalence_rate"] < minimum_equivalence_rate:
        failures.append("equivalence rate below threshold")
    if metrics["ocr_text_match_mean"] < minimum_text_match:
        failures.append("OCR text match below threshold")
    if metrics["translation_match_mean"] < minimum_text_match:
        failures.append("translation match below threshold")
    return {"passed": not failures, "metrics": metrics, "failures": failures}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at line {line_number}: {exc}") from exc
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--minimum-samples", type=int, default=10)
    args = parser.parse_args()
    result = evaluate_records(load_jsonl(args.path), minimum_samples=args.minimum_samples)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
