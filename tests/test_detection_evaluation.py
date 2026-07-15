from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from backend.engines.detection.evaluation import (
    DetectionCase,
    box_iou,
    evaluate_detection_cases,
)


def test_box_iou_handles_overlap_and_disjoint_boxes():
    assert box_iou([0, 0, 10, 10], [5, 5, 15, 15]) == pytest.approx(25 / 175)
    assert box_iou([0, 0, 10, 10], [20, 20, 30, 30]) == 0.0


def test_detection_metrics_report_recall_precision_and_split_merge():
    cases = [
        DetectionCase("exact", ((0, 0, 10, 10),), ((0, 0, 10, 10),), "baseline"),
        DetectionCase("miss", ((20, 0, 30, 10),), (), "miss"),
        DetectionCase("false_positive", (), ((40, 0, 50, 10),), "false_positive"),
        DetectionCase("split", ((60, 0, 100, 10),), ((60, 0, 80, 10), (80, 0, 100, 10)), "split_merge"),
        DetectionCase("merge", ((110, 0, 125, 10), (120, 0, 135, 10)), ((110, 0, 135, 10),), "split_merge"),
    ]

    metrics = evaluate_detection_cases(cases)

    assert metrics.true_positive == 3
    assert metrics.false_positive == 2
    assert metrics.false_negative == 2
    assert metrics.precision == pytest.approx(0.6)
    assert metrics.recall == pytest.approx(0.6)
    assert metrics.split_count == 1
    assert metrics.merge_count == 1
    assert metrics.by_category["split_merge"]["split_count"] == 1


def test_detection_benchmark_script_emits_json(tmp_path):
    corpus = tmp_path / "corpus.json"
    corpus.write_text(
        json.dumps([
            {
                "id": "one",
                "category": "baseline",
                "expected_boxes": [[0, 0, 10, 10]],
                "predicted_boxes": [[0, 0, 10, 10]],
            }
        ]),
        encoding="utf-8",
    )
    output = tmp_path / "metrics.json"

    result = subprocess.run(
        [sys.executable, "scripts/benchmark_detection_recall.py", str(corpus), "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout)["recall"] == 1.0
    assert json.loads(output.read_text(encoding="utf-8"))["precision"] == 1.0
