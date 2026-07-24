#!/usr/bin/env python3
"""Run deterministic golden-image boundary and resource regression checks.

This intentionally does not claim model accuracy. Licensed image/model runs can
use the same case IDs, while this repository-safe benchmark verifies import,
decode, digest, timing, and peak Python allocation behavior.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

import cv2
import numpy as np

# Allow direct execution from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.infrastructure.image.import_validation import validate_image_for_import


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "fixtures" / "golden_image_corpus.json"


def _make_image(case: dict) -> np.ndarray:
    height, width = int(case["height"]), int(case["width"])
    image = np.full((height, width, 3), 255, dtype=np.uint8)
    pattern = case["pattern"]
    if pattern == "panels":
        for y in range(0, height, max(80, height // 8)):
            image[y : y + 3, :, :] = (120, 120, 120)
    elif pattern == "bubbles":
        for index in range(4):
            x1, y1 = 40 + index * 90, 60 + index * 150
            cv2.ellipse(image, (x1 + 110, y1 + 70), (110, 70), 0, 0, 360, (245, 245, 245), -1)
            cv2.ellipse(image, (x1 + 110, y1 + 70), (110, 70), 0, 0, 360, (30, 30, 30), 2)
    elif pattern == "low_contrast":
        image[:] = (224, 224, 224)
        image[height // 3 : height // 3 + 4, width // 5 : width * 4 // 5] = (190, 190, 190)
    elif pattern == "sfx":
        cv2.putText(image, "SFX", (80, height // 2), cv2.FONT_HERSHEY_SIMPLEX, 3, (30, 30, 180), 5)
    elif pattern == "unicode":
        cv2.rectangle(image, (70, 100), (width - 70, height - 100), (235, 235, 235), 3)
    return image


def _percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int((len(ordered) - 1) * ratio))], 4)


def run(*, repeat: int = 3, baseline: dict | None = None) -> dict:
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    results = []
    with tempfile.TemporaryDirectory(prefix="vibecleaner-golden-") as directory:
        for case in corpus["cases"]:
            image = _make_image(case)
            path = Path(directory) / f"{case['case_id']}.png"
            assert cv2.imwrite(str(path), image)
            timings: list[float] = []
            peaks: list[int] = []
            report = None
            digest = hashlib.sha256(np.ascontiguousarray(image).data).hexdigest()
            for _ in range(max(1, repeat)):
                tracemalloc.start()
                started = time.perf_counter()
                report, issues = validate_image_for_import(str(path))
                elapsed = (time.perf_counter() - started) * 1000
                _current, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                if report is None or issues:
                    raise RuntimeError(f"golden case {case['case_id']} failed validation: {issues}")
                timings.append(elapsed)
                peaks.append(peak)
            results.append({
                "case_id": case["case_id"],
                "category": case["category"],
                "digest": digest,
                "width": report["width"],
                "height": report["height"],
                "time_ms": {"p50": _percentile(timings, 0.50), "p95": _percentile(timings, 0.95)},
                "peak_python_bytes": max(peaks),
            })
    output = {"schema_version": 1, "corpus_id": corpus["corpus_id"], "repeat": repeat, "cases": results}
    if baseline:
        regressions = []
        baseline_cases = {item["case_id"]: item for item in baseline.get("cases", [])}
        for item in results:
            previous = baseline_cases.get(item["case_id"])
            if not previous:
                continue
            for metric in ("p50", "p95"):
                old = float(previous["time_ms"].get(metric, 0))
                new = float(item["time_ms"].get(metric, 0))
                if old > 0 and new > old * 1.25:
                    regressions.append({"case_id": item["case_id"], "metric": f"time_ms.{metric}", "baseline": old, "current": new})
            old_memory = int(previous.get("peak_python_bytes", 0))
            if old_memory > 0 and item["peak_python_bytes"] > old_memory * 1.25:
                regressions.append({"case_id": item["case_id"], "metric": "peak_python_bytes", "baseline": old_memory, "current": item["peak_python_bytes"]})
        output["regressions"] = regressions
        output["passed"] = not regressions
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text(encoding="utf-8")) if args.baseline else None
    result = run(repeat=args.repeat, baseline=baseline)
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0 if result.get("passed", True) else 2


if __name__ == "__main__":
    raise SystemExit(main())
