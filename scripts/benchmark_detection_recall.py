#!/usr/bin/env python3
"""Evaluate detection predictions against a box-only JSON corpus.

The corpus deliberately stores boxes rather than source images. This keeps the
benchmark safe to share and lets the same evaluator consume licensed data,
synthetic fixtures, or predictions captured from a local model run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.engines.detection.evaluation import DetectionCase, evaluate_detection_cases


def _load_cases(path: Path) -> list[DetectionCase]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("cases", [])
    if not isinstance(payload, list):
        raise ValueError("Detection corpus must be a JSON list or an object with a cases list")
    return [DetectionCase.from_mapping(item) for item in payload]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path, help="JSON corpus with expected_boxes and predicted_boxes")
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    metrics = evaluate_detection_cases(
        _load_cases(args.corpus),
        iou_threshold=args.iou_threshold,
    ).as_dict()
    encoded = json.dumps(metrics, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
