#!/usr/bin/env python3
"""Capture RT-DETR predictions for a detection evaluation corpus.

Input cases contain ``image_path`` and ``expected_boxes``. The output keeps the
annotations and adds model ``predicted_boxes`` and ``predicted_confidences`` so
it can be passed directly to ``benchmark_detection_recall.py``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.engines.detection.wrapper import RTDETRv2Detector


def _box_from_block(block: Any) -> list[int]:
    values = getattr(block, "xyxy", None)
    if values is None:
        raise ValueError(f"Detection block has no xyxy coordinates: {block!r}")
    if hasattr(values, "tolist"):
        values = values.tolist()
    return [int(round(float(values[index]))) for index in range(4)]


def predictions_from_blocks(blocks: list[Any]) -> tuple[list[list[int]], list[float | None]]:
    boxes: list[list[int]] = []
    confidences: list[float | None] = []
    for block in blocks:
        boxes.append(_box_from_block(block))
        value = getattr(block, "confidence", None)
        confidences.append(float(value) if value is not None else None)
    return boxes, confidences


def _load_cases(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return {"schema_version": 1}, payload
    if isinstance(payload, dict) and isinstance(payload.get("cases"), list):
        metadata = {key: value for key, value in payload.items() if key != "cases"}
        return metadata, list(payload["cases"])
    raise ValueError("Detection corpus must be a JSON list or an object with a cases list")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path, help="JSON corpus containing image_path and expected_boxes")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="High Precision (FP32)")
    parser.add_argument("--confidence-threshold", type=float, default=0.45)
    parser.add_argument("--no-tiling", action="store_true")
    args = parser.parse_args()

    metadata, cases = _load_cases(args.corpus)
    detector = RTDETRv2Detector()
    output_cases: list[dict[str, Any]] = []
    for index, original in enumerate(cases, 1):
        if not isinstance(original, dict):
            raise ValueError(f"Corpus case {index} must be an object")
        image_value = original.get("image_path")
        if not image_value:
            raise ValueError(f"Corpus case {index} is missing image_path")
        image_path = Path(str(image_value))
        if not image_path.is_absolute():
            image_path = args.corpus.parent / image_path
        if not image_path.exists():
            raise FileNotFoundError(f"Corpus image does not exist: {image_path}")

        with Image.open(image_path) as source:
            rgb = np.asarray(source.convert("RGB"), dtype=np.uint8)
        bgr = rgb[:, :, ::-1].copy()
        blocks = detector.detect_bubbles(
            bgr,
            model_name=args.model,
            confidence_threshold=args.confidence_threshold,
            tiling_enabled=not args.no_tiling,
        )
        predicted_boxes, predicted_confidences = predictions_from_blocks(blocks)
        captured = dict(original)
        captured["image_path"] = str(image_path)
        captured["predicted_boxes"] = predicted_boxes
        captured["predicted_confidences"] = predicted_confidences
        output_cases.append(captured)

    metadata.update({
        "schema_version": 2,
        "prediction_metadata": {
            "engine": "rtdetr_v2_onnx",
            "model": args.model,
            "confidence_threshold": args.confidence_threshold,
            "tiling_enabled": not args.no_tiling,
        },
        "cases": output_cases,
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Captured {len(output_cases)} detection cases to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
